# Runtime 运行时

`mmagent` 是 Windows 11 与 Linux/WSL 进程监督器，不是 socket 服务。每个 case 有一个 SQLite 状态库、不可变尝试日志、固定任务工作区和一条出版路径。任务成功只表示进程完成，不表示科学结论有效或已获人工批准。

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

