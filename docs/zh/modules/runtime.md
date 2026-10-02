# Runtime 运行时

`mmagent` 是 Windows 11 与 Linux/WSL 进程监督器，不是 socket 服务。每个 case 有一个 SQLite 状态库、不可变尝试日志、固定任务工作区和一条出版路径。任务成功只表示进程完成，不表示科学结论有效或已获人工批准。

## 自动选择主机实现

只有一套源码和 CLI，不要求用户选择不同产品版本。无论 Codex 操作会话调用 CLI，还是高级用户直接运行 `uv run mmagent`，`runtime/platform.py` 都按当前 Python 解释器的 `os.name` 确定性选择底层实现：原生 Windows Python 为 `"nt"`，Linux/WSL 内的 Python 走 POSIX 分支。WSL 的宿主机是 Windows，不会改变 WSL 内解释器的选择。

`pyproject.toml` 中的 `sys_platform == 'win32'` 依赖条件让 `uv sync --locked` 只在 Windows 安装 `pywin32`，对应导入也只在 Windows 分支执行。SQLite 状态、任务 schema、CLI 命令和人工决定契约共用；不需要 Codex 判断代码版本，也不需要模型调用来做平台选择。

| 底层能力 / 所属函数 | Windows（`os.name == "nt"`） | Linux/WSL（当前非 Windows 实现） |
| --- | --- | --- |
| 发布锁 / `publication_lock` | 带阻塞重试的单字节 `msvcrt` 锁 | `fcntl.flock` |
| PID 身份 / `process_start_ticks` | Win32 进程等待状态与创建时间 | `/proc/<pid>/stat` 启动 ticks |
| 启动 / `process_options`、`own_process` | 挂起进程组、加入命名 Job Object、恢复主线程 | 新 session / 进程组 |
| 取消 / `signal_process_group` | 控制台 break，随后结束整个 job | 向进程组发送 SIGINT、SIGTERM、SIGKILL |
| 程序 / `executable_command` | 解析 PATH/PATHEXT、任务 PATH 和明确的相对路径 | 将 argv 交给原有 subprocess 路径 |
| 链接 / `is_link` | 拒绝符号链接及 junction | 拒绝符号链接 |
| 字体 / `cli._font_check` | Fontconfig，再回退到 Windows 字体注册表 | 原有 fontconfig 检查 |

自动选择不等于翻译任意任务 argv/shell 语法、安装系统工具、改写 provider 配置或迁移已保存的绝对路径。任务命令和工具版本仍须适合解释器所在主机；双系统 shell 示例见[环境配置](../setup.md)。

## 平台报错与维护

先运行 `rtk uv run mmagent doctor [CASE]` 和 `rtk uv run mmagent status CASE TASK`。检查任务 `error` 与 attempt 记录，再查对应 `CASE/tasks/<id>/runtime-runs/<run-id>/stderr.log` 和 `events.jsonl`；不能仅凭 PID 存活断言成功。`.runtime/state.sqlite` 拥有任务/attempt 状态，`.runtime/publish.lock` 负责发布串行化；不要手改数据库。

- `process_start`：检查程序解析及 Windows 日志中的 Job Object/主线程错误。建立所有权失败时适配层会回收子进程。
- `stale_command_run`：退出状态已丢失；先检查保存的输出，再明确接续。PID 本身不是安全的进程身份。
- 链接/路径拒绝：检查符号链接、junction 和解析后的 case 边界；不要关闭验证或仅为绕过它要求管理员权限。
- 字体/TeX/Poppler 缺失：需要出版时补齐对应主机依赖；doctor 不证明 PDF 构建或实时 provider session 可用。

源码拥有者与针对性测试命令见[开发交接](../dev.md)；Windows 实测证据和 Linux 未重新测试的边界见[当前状态](../status.md)。`tests/runtime/test_platform.py` 覆盖本机原语与恢复，scheduler、CLI、artifact、input 测试覆盖调用方；这些都是本地测试，不是完整建模运行。

## macOS 边界

非 Windows 不代表支持所有 Unix 主机。macOS 当前会进入 POSIX 分支，但 `process_start_ticks` 仍读取 Linux `/proc/<pid>/stat`，标准 macOS 不提供该接口。没有进程身份时，重启协调可能把存活运行误判为已结束；仅文件锁和信号可用不足以证明完整兼容。

后续需增加明确的 Darwin 进程身份实现（例如 Apple 的 [libproc API](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/libproc/libproc.h)），验证 PID 复用防护、存活运行取消和重启恢复，并检查 macOS 的工具/字体发现。本次文档更新没有增加 macOS 适配器或实机测试，也不意味着 Windows/Linux case 的绝对路径可直接迁移。

## Case 与任务

使用 `uv run mmagent init CASE` 创建 case，在 `CASE/case.toml` 中选择并发限制、沙箱策略、无凭据模型档位和本地工具。Provider 与认证设置保留在用户 Codex 配置中，不会复制到 case 数据库或 doctor 输出。

用 `uv run mmagent submit CASE task.json` 提交任务，再运行 `uv run mmagent serve CASE`。命令任务使用 `kind: "command"` 和 argv 字符串列表；agent 任务使用 `kind: "agent"`、prompt 以及 case profile 名称，或显式的 `model` 与 `effort`。两者都可以声明相对 case 的 `inputs`；agent 任务还可指定 instructions 和 skills。进程始终在 `tasks/<id>/workspace/` 中运行。

受管 Codex 调用使用 JSONL、`approval_policy=never`、case 沙箱、`project_doc_max_bytes=0` 以及选定档位。恢复覆盖项放在 `resume` 之后。即使项目文档被禁用，受管 prompt 仍会带入 rtk/uv/bun 规则和精确人工决定规则。

## 状态与恢复

状态包括 `queued`、`running`、`retry_wait`、`paused`、`succeeded`、`failed` 和 `cancelled`。每次主机尝试都有独立的 `runtime-runs/<run-id>/events.jsonl` 与 `stderr.log`，并在 SQLite 中保存 PID/进程组身份。

临时子任务失败时会立即在同一 Codex session 中恢复一次；第二次失败至少等待 300 秒，并遵守更长的有效 `Retry-After`；第三次暂停。主 session 也只做一次即时同 session 重试。认证、配置、超时、未知 session 和其他非临时错误不会自动切换 provider 或 session。

`mmagent cancel` 会保存取消意图。Linux/WSL 按 SIGINT、SIGTERM、SIGKILL 顺序结束进程组。Windows 先挂起创建新进程组、加入按 run ID 命名的 Job Object，再恢复主线程，避免子孙进程先于所有权建立启动。取消时尝试 CTRL_BREAK_EVENT，两秒宽限后强制结束整个 job；没有可用控制台时仍能强制回收。根进程退出或 supervisor 被结束时，关闭 job 也会回收子孙进程。建立所有权失败会记录 `process_start` 错误并回收挂起子进程。

重启协调会校验 Linux `/proc` 启动 ticks 或 Windows 进程创建时间；保存的身份值与主机平台绑定。Windows 通过 run ID 打开对应 job，不按任意 PID 杀进程。不会接管任意进程；完整 agent 日志可被接受为成功，丢失命令退出状态的死任务则暂停。每个 case 仍只运行一个 supervisor，这不代表支持跨系统绝对路径迁移。

## 协调器输出

Agent 可以在 `workspace/RESULT.json` 中写入 `requests`、`wait_for` 和 `deliverables`。协调器在子任务完成后使用 `State.resume(task_id, followup=...)` 继续原 session；这属于正常后续，不是失败重试。成功的 deliverable 会通过 `publish_bundle` 发送并记录收据。

## 发布与诊断

`publish_bundle` 会拒绝符号链接、Windows junction、路径逃逸、保留临时名以及检查期间变化的文件，并校验清单、大小和哈希。选定输入树也会拒绝符号链接和 junction。发布锁在 Linux/WSL 使用 `fcntl.flock`，Windows 使用带阻塞重试的单字节 `msvcrt` 锁；持锁进程退出后由系统释放。

`uv run mmagent doctor [CASE]` 检查 Codex、uv、bun、rtk、XeLaTeX、latexmk、BibTeX、CTeX/xeCJK/zhnumber、CJK 字体、Poppler 和 case 工具。Windows 程序解析遵循 `PATH`/`PATHEXT`，支持任务独立 `PATH` 及明确相对任务工作目录的程序路径；命令输出按 UTF-8 解码并替换不可解码字节。fontconfig 找不到所需字体时可回退到 Windows 字体注册表。不会发起实时 provider 请求，也不会读取或打印凭据。

