"""Public ``mmagent`` command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys

from . import control
from .contracts import read_json, sha256_file, write_json
from .evidence.cli import add_evidence_parser
from .execution import finalize_experiment, prepare_experiment, run_experiment, submit_experiment
from .publication.cli import add_publication_parser
from .runtime.config import ConfigError, init_case, load_case_config
from .runtime.scheduler import Supervisor
from .runtime.state import State, TaskNotFound
from .workflow import Coordinator, submit_coordinator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mmagent")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init = subcommands.add_parser("init", help="create a case workspace")
    init.add_argument("case_root", type=Path)

    submit = subcommands.add_parser("submit", help="submit a JSON task spec")
    submit.add_argument("case_root", type=Path)
    submit.add_argument("spec", help="JSON file path, or - for stdin")

    status = subcommands.add_parser("status", help="show canonical task state")
    status.add_argument("case_root", type=Path)
    status.add_argument("task_id", nargs="?")

    resume = subcommands.add_parser("resume", help="queue a task or same-session follow-up")
    resume.add_argument("case_root", type=Path)
    resume.add_argument("task_id")
    followups = resume.add_mutually_exclusive_group()
    followups.add_argument("--followup")
    followups.add_argument("--followup-file", type=Path)

    cancel = subcommands.add_parser("cancel", help="cancel a task")
    cancel.add_argument("case_root", type=Path)
    cancel.add_argument("task_id")

    serve = subcommands.add_parser("serve", help="run the local supervisor")
    serve.add_argument("case_root", type=Path)
    serve.add_argument("--once", action="store_true")
    serve.add_argument("--stop-when-idle", action="store_true")
    serve.add_argument("--poll-interval", type=float)

    doctor = subcommands.add_parser("doctor", help="inspect local runtime tools without network calls")
    doctor.add_argument("case_root", type=Path, nargs="?")

    start = subcommands.add_parser("start", help="start a human-authorized coordinator")
    start.add_argument("case_root", type=Path)
    start.add_argument("task_id")
    prompts = start.add_mutually_exclusive_group(required=True)
    prompts.add_argument("--prompt")
    prompts.add_argument("--prompt-file", type=Path)
    start.add_argument("--input", action="append", default=[])
    start.add_argument("--profile", required=True)
    start.add_argument("--tier-decision", required=True)

    workflow = subcommands.add_parser("workflow", help="advance coordinator handoffs")
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)
    poll = workflow_commands.add_parser("poll", help="poll and continue one coordinator")
    poll.add_argument("case_root", type=Path)
    poll.add_argument("task_id")
    poll.set_defaults(handler=lambda args: Coordinator(args.case_root).poll(args.task_id))

    _add_human_parser(subcommands)
    _add_experiment_parser(subcommands)
    add_evidence_parser(subcommands)
    add_publication_parser(subcommands)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            root = init_case(args.case_root)
            State(root)
            control.initialize(root)
            _print({"case_root": str(root), "initialized": True})
        elif args.command == "submit":
            spec = json.load(sys.stdin) if args.spec == "-" else read_json(args.spec)
            task_id = State(args.case_root).submit(spec)
            _print({"task_id": task_id})
        elif args.command == "status":
            state = State(args.case_root)
            _print(state.get_task(args.task_id) if args.task_id else state.list_tasks())
        elif args.command == "resume":
            followup = args.followup
            if args.followup_file:
                followup = args.followup_file.read_text(encoding="utf-8")
            State(args.case_root).resume(args.task_id, followup)
            _print({"task_id": args.task_id, "state": "queued"})
        elif args.command == "cancel":
            State(args.case_root).cancel(args.task_id)
            _print({"task_id": args.task_id, "cancel_requested": True})
        elif args.command == "serve":
            supervisor = Supervisor(args.case_root)

            def stop(_signum, _frame):
                supervisor.request_stop()

            signal.signal(signal.SIGINT, stop)
            signal.signal(signal.SIGTERM, stop)
            if args.once:
                interval = args.poll_interval or supervisor.config.poll_interval
                if interval <= 0:
                    raise ValueError("poll_interval must be positive")
                while True:
                    supervisor.run_once()
                    if not supervisor.active:
                        break
                    supervisor.sleeper(interval)
            else:
                supervisor.serve(
                    poll_interval=args.poll_interval,
                    stop_when_idle=args.stop_when_idle,
                )
        elif args.command == "doctor":
            _print(doctor(args.case_root))
        elif args.command == "start":
            _print(_start_coordinator(args))
        elif hasattr(args, "handler"):
            _print(args.handler(args))
        return 0
    except (ConfigError, FileExistsError, KeyError, TaskNotFound, ValueError, RuntimeError, OSError) as exc:
        print(f"mmagent: {exc}", file=sys.stderr)
        return 2


def doctor(case_root: Path | None = None) -> dict:
    checks = {}
    for name, command in (
        ("codex", ["codex", "--version"]),
        ("uv", ["uv", "--version"]),
        ("bun", ["bun", "--version"]),
        ("rtk", ["rtk", "--version"]),
        ("xelatex", ["xelatex", "--version"]),
        ("latexmk", ["latexmk", "--version"]),
        ("bibtex", ["bibtex", "--version"]),
        ("kpsewhich", ["kpsewhich", "--version"]),
        ("pdftotext", ["pdftotext", "-v"]),
        ("pdfinfo", ["pdfinfo", "-v"]),
        ("pdffonts", ["pdffonts", "-v"]),
        ("pdftoppm", ["pdftoppm", "-v"]),
    ):
        checks[name] = _tool_check(command)
    result = {
        "checks": checks,
        "poppler_available": checks["pdftotext"]["available"] and checks["pdfinfo"]["available"],
        "tex_files": {
            name: _content_check(["kpsewhich", name])
            for name in ("ctex.sty", "xeCJK.sty", "zhnumber.sty")
        },
        "fonts": {
            name: _font_check(name)
            for name in ("Noto Serif CJK SC", "Noto Sans CJK SC")
        },
        "network_checked": False,
        "credentials_inspected": False,
        "limitations": [
            "workspace-write does not isolate secrets from another process running as the same Linux user",
            "provider authentication and endpoint configuration are inherited from user-level Codex configuration",
        ],
    }
    if case_root is not None:
        config = load_case_config(case_root)
        result["case"] = {
            "case_root": str(config.case_root),
            "local_slots": config.local_slots,
            "sandbox": config.sandbox,
            "allow_network": config.allow_network,
            "profiles": sorted(config.profiles),
            "configured_tools": {
                name: {"command": command, "available": shutil.which(command) is not None}
                for name, command in config.tools.items()
            },
        }
    return result


def _tool_check(command: list[str]) -> dict:
    executable = shutil.which(command[0])
    if executable is None:
        return {"available": False, "executable": None, "version": None}
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False,
        )
        first_line = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        first_line = f"unavailable: {type(exc).__name__}"
    return {"available": True, "executable": executable, "version": first_line[:300] or None}


def _content_check(command: list[str]) -> dict:
    executable = shutil.which(command[0])
    if executable is None:
        return {"available": False, "value": None}
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=5,
        check=False,
    )
    value = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), "")
    return {"available": completed.returncode == 0 and bool(value), "value": value[:500] or None}


def _font_check(name: str) -> dict:
    result = _content_check(["fc-match", "-f", "%{family}\n", name])
    result["available"] = result["available"] and name.lower() in (result["value"] or "").lower()
    return result


def _add_human_parser(subcommands) -> None:
    parser = subcommands.add_parser("human", help="manage explicit human questions and decisions")
    commands = parser.add_subparsers(dest="human_command", required=True)

    tier = commands.add_parser("ask-tier", help="ask to confirm fast, standard, or full")
    tier.add_argument("case_root", type=Path)
    tier.add_argument("tier", choices=("fast", "standard", "full"))
    tier.add_argument("--problem", default="problem/question.md")
    tier.set_defaults(handler=_ask_tier)

    ask = commands.add_parser("ask", help="append a fixed-object question from JSON")
    ask.add_argument("case_root", type=Path)
    ask.add_argument("request", type=Path)
    ask.set_defaults(handler=lambda args: control.ask_human(args.case_root, **read_json(args.request)))

    disclosure = commands.add_parser("ask-ai-disclosure", help="review exact AI adoption facts")
    disclosure.add_argument("case_root", type=Path)
    disclosure.add_argument("task_id")
    disclosure.add_argument("--adoption", required=True)
    disclosure.add_argument("--modification", required=True)
    disclosure.add_argument("--verification", required=True)
    disclosure.set_defaults(handler=_ask_ai_disclosure)

    answer = commands.add_parser("answer", help="append a human answer")
    answer.add_argument("case_root", type=Path)
    answer.add_argument("question_id")
    answer_text = answer.add_mutually_exclusive_group(required=True)
    answer_text.add_argument("--text")
    answer_text.add_argument("--file", type=Path)
    answer.set_defaults(handler=_capture_answer)

    refresh = commands.add_parser("refresh", help="consume complete answer sections")
    refresh.add_argument("case_root", type=Path)
    refresh.set_defaults(handler=lambda args: control.consume_answers(args.case_root))

    decide = commands.add_parser("decide", help="record one explicitly named displayed choice")
    decide.add_argument("case_root", type=Path)
    decide.add_argument("question_id")
    decide.add_argument("answer_id")
    decide.add_argument("choice")
    decide.set_defaults(
        handler=lambda args: control.record_human_decision(
            args.case_root,
            question_id=args.question_id,
            answer_id=args.answer_id,
            choice=args.choice,
        )
    )

    adoption = commands.add_parser("ai-adoption", help="record reviewed AI adoption facts")
    adoption.add_argument("case_root", type=Path)
    adoption.add_argument("decision_id")
    adoption.add_argument("task_id")
    adoption.add_argument("--adoption", required=True)
    adoption.add_argument("--modification", required=True)
    adoption.add_argument("--verification", required=True)
    adoption.set_defaults(handler=_record_ai_adoption)

    pending = commands.add_parser("pending", help="list unresolved human questions")
    pending.add_argument("case_root", type=Path)
    pending.set_defaults(handler=lambda args: control.pending_questions(args.case_root))


def _add_experiment_parser(subcommands) -> None:
    parser = subcommands.add_parser("experiment", help="prepare, run, and finalize experiments")
    commands = parser.add_subparsers(dest="experiment_command", required=True)

    prepare = commands.add_parser("prepare", help="validate and freeze an experiment request")
    prepare.add_argument("case_root", type=Path)
    prepare.add_argument("request", type=Path)
    prepare.add_argument("--output", type=Path)
    prepare.set_defaults(handler=_prepare_experiment)

    submit = commands.add_parser("submit", help="submit a prepared experiment")
    submit.add_argument("case_root", type=Path)
    submit.add_argument("prepared", type=Path)
    submit.set_defaults(
        handler=lambda args: {
            "task_id": submit_experiment(args.case_root, read_json(args.prepared))
        }
    )

    finalize = commands.add_parser("finalize", help="publish a completed experiment result")
    finalize.add_argument("case_root", type=Path)
    finalize.add_argument("task_id")
    finalize.set_defaults(handler=lambda args: finalize_experiment(args.case_root, args.task_id))

    run = commands.add_parser("run", help="run and finalize one experiment synchronously")
    run.add_argument("case_root", type=Path)
    run.add_argument("request", type=Path)
    run.set_defaults(handler=lambda args: run_experiment(args.case_root, read_json(args.request)))


def _ask_tier(args) -> dict:
    root = args.case_root.resolve()
    config = load_case_config(root)
    profile = config.profile(args.tier)
    problem = (root / args.problem).resolve()
    if not problem.is_file() or not problem.is_relative_to(root):
        raise ValueError("problem must be a case-relative existing file")
    displayed = {
        "tier": args.tier,
        "profile": {"model": profile.model, "effort": profile.effort},
        "problem": {
            "path": problem.relative_to(root).as_posix(),
            "sha256": sha256_file(problem),
        },
    }
    return control.ask_human(
        root,
        scope="research_scope",
        displayed=displayed,
        prompt=f"请确认对该题目采用 {args.tier} 档，或选择 reject。",
        choices=[args.tier, "reject"],
        approval_choices=[args.tier],
        limits={"bounds": {"tier": args.tier}},
    )


def _ask_ai_disclosure(args) -> dict:
    displayed = {
        "task_id": args.task_id,
        "adoption": args.adoption.strip(),
        "modification": args.modification.strip(),
        "human_verification": args.verification.strip(),
    }
    return control.ask_human(
        args.case_root,
        scope="ai_disclosure",
        displayed=displayed,
        prompt="请确认这些 AI 采纳、修改和人工核验事实准确，或选择 reject。",
        choices=["confirm", "reject"],
        approval_choices=["confirm"],
    )


def _capture_answer(args) -> dict:
    text = args.text if args.text is not None else args.file.read_text(encoding="utf-8")
    return {"answer_id": control.capture_human_answer(args.case_root, args.question_id, text)}


def _record_ai_adoption(args) -> dict:
    return control.record_ai_adoption(
        args.case_root,
        disclosure_decision_id=args.decision_id,
        task_id=args.task_id,
        adoption=args.adoption,
        modification=args.modification,
        human_verification=args.verification,
    )


def _prepare_experiment(args) -> dict:
    prepared = prepare_experiment(args.case_root, read_json(args.request))
    if args.output is not None:
        write_json(args.output, prepared)
        return {"prepared": str(args.output.resolve()), "task_id": prepared["task_id"]}
    return prepared


def _start_coordinator(args) -> dict:
    authorization = control.decision(args.case_root, args.tier_decision)
    if authorization["scope"] != "research_scope" or authorization["status"] != "approved":
        raise ValueError("tier decision is not an approved research_scope decision")
    if authorization["choice"] != args.profile:
        raise ValueError("profile differs from the human-selected tier")
    selected = authorization.get("displayed", {})
    if not isinstance(selected, dict) or not isinstance(selected.get("problem"), dict):
        raise ValueError("tier decision was not created by human ask-tier")
    profile = load_case_config(args.case_root).profile(args.profile)
    if selected.get("profile") != {"model": profile.model, "effort": profile.effort}:
        raise ValueError("selected profile changed after the human decision")
    problem = selected.get("problem", {})
    if not isinstance(problem.get("path"), str):
        raise ValueError("tier decision has no problem reference")
    problem_path = (args.case_root.resolve() / problem["path"]).resolve()
    if (
        not problem_path.is_file()
        or not problem_path.is_relative_to(args.case_root.resolve())
        or problem.get("sha256") != sha256_file(problem_path)
    ):
        raise ValueError("problem statement changed after the human decision")
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    task_id = submit_coordinator(
        args.case_root,
        task_id=args.task_id,
        prompt=prompt,
        inputs=args.input,
        profile=args.profile,
    )
    return {"task_id": task_id, "profile": args.profile, "tier_decision": args.tier_decision}


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
