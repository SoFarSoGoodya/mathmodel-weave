"""Host-specific publication locks and supervised process ownership."""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import errno
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


def executable_command(command: list[str], *, cwd: str | Path | None = None, env: dict[str, str] | None = None) -> list[str]:
    if os.name != "nt":
        return command
    program = command[0]
    if cwd is not None and os.path.dirname(program) and not os.path.isabs(program):
        program = str(Path(cwd) / program)
    executable = shutil.which(program, path=env.get("PATH") if env is not None else None)
    return [executable or program, *command[1:]]


def is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


@contextmanager
def publication_lock(path: Path):
    with path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            if lock.seek(0, os.SEEK_END) == 0:
                lock.write(b"\0")
                lock.flush()
            while True:
                lock.seek(0)
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                        raise
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX)
            yield


def process_start_ticks(pid: int) -> int | None:
    if os.name == "nt":
        import pywintypes
        import win32api
        import win32con
        import win32event
        import win32process

        try:
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, pid)
            try:
                if win32event.WaitForSingleObject(handle, 0) != win32con.WAIT_TIMEOUT:
                    return None
                created = win32process.GetProcessTimes(handle)["CreationTime"]
                return int(created.timestamp() * 1_000_000)
            finally:
                handle.Close()
        except pywintypes.error:
            return None
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
        return int(fields[19])
    except (FileNotFoundError, IndexError, ValueError, PermissionError, ProcessLookupError):
        return None


def process_options() -> dict:
    if os.name == "nt":
        import win32con

        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | win32con.CREATE_SUSPENDED}
    return {"start_new_session": True}


def own_process(process: subprocess.Popen, run_id: str):
    if os.name != "nt":
        return None
    import win32job

    job = None
    try:
        job = win32job.CreateJobObject(None, f"mmagent-{run_id}")
        limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        limits["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
        win32job.AssignProcessToJobObject(job, int(process._handle))
        _resume_process(process.pid)
    except BaseException as exc:
        if job is not None:
            job.Close()
        if process.poll() is None:
            process.kill()
        process.wait()
        if isinstance(exc, Exception):
            raise RuntimeError(f"could not establish Windows process ownership: {exc}") from exc
        raise
    return job


def _resume_process(pid: int) -> None:
    import win32api
    import win32con
    import win32process

    class ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD), ("usage", wintypes.DWORD),
            ("thread_id", wintypes.DWORD), ("process_id", wintypes.DWORD),
            ("base_priority", wintypes.LONG), ("delta_priority", wintypes.LONG),
            ("flags", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Thread32First", "Thread32Next"):
        function = getattr(kernel, name)
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
        function.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(4, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ThreadEntry()
        entry.size = ctypes.sizeof(entry)
        available = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while available:
            if entry.process_id == pid:
                thread = win32api.OpenThread(win32con.THREAD_SUSPEND_RESUME, False, entry.thread_id)
                try:
                    win32process.ResumeThread(thread)
                finally:
                    thread.Close()
                return
            available = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        raise RuntimeError(f"no suspended primary thread for PID {pid}")
    finally:
        kernel.CloseHandle(snapshot)


def process_group(pid: int) -> int:
    return pid if os.name == "nt" else os.getpgid(pid)


def signal_process_group(pid: int, stage: int, *, job=None, run_id: str | None = None) -> None:
    if os.name == "nt":
        import pywintypes
        import win32job

        if stage == 1:
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            except OSError:
                pass
            return
        if job is not None:
            win32job.TerminateJobObject(job, 1)
        elif run_id is not None:
            try:
                handle = win32job.OpenJobObject(win32job.JOB_OBJECT_TERMINATE, False, f"mmagent-{run_id}")
                try:
                    win32job.TerminateJobObject(handle, 1)
                finally:
                    handle.Close()
            except pywintypes.error as exc:
                if exc.winerror != 2:
                    raise
        return
    try:
        os.killpg(pid, (signal.SIGINT, signal.SIGTERM, signal.SIGKILL)[stage - 1])
    except ProcessLookupError:
        pass
