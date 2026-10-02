# 环境配置与换系统恢复

## 恢复产品研发

克隆或恢复本产品仓库，进入根目录。源码要求 Python 3.12 或更新；runtime supervisor 支持原生 Windows 11 与 Linux/WSL。Python 依赖由 `uv` 和已跟踪的 `uv.lock` 管理；`pywin32` 仅在 Windows 安装。可选 Node 工具使用 `bun`，日常 shell 使用 `rtk`。不要靠复制旧虚拟环境安装依赖。

```text
rtk uv sync --locked
rtk uv run mmagent --help
rtk uv run mmagent doctor
```

Doctor 检查本机 Codex、uv、bun、rtk、XeLaTeX/latexmk/BibTeX、CTeX/xeCJK/zhnumber、Noto CJK 字体和 Poppler。`rtk uv run mmagent doctor CASE_DIR` 还检查 case 配置与配置的工具可执行程序。它不负责登录、不检查凭据、不请求实时 provider、不运行 MCP、不验证模型可用性，也不证明 resume 能成功。缺少出版依赖可在需要出版工作时补齐；继承的成功 PDF 不代表这台主机能重新构建。

Codex/provider 配置、profiles、凭据和 MCP 登录属于用户可信本机环境。产品不安装或重写全局认证/配置。请自行重建或安全恢复，勿把秘密发进聊天、写入 Git、case TOML/JSON/Markdown 或人工回答。系统字体和 TeX 宏包需另行恢复。包含所需宏包的自定义 TeX 树是主机依赖，不一定是可丢弃缓存。

## 原生 Windows

在 PowerShell 中运行相同的环境引导命令。Codex CLI、uv、rtk 应安装 Windows 版本并加入 `PATH`；可选 bun、TeX 与 Poppler 也需要 Windows 可执行程序。Doctor 会解析程序路径并检查命令退出状态。字体检查优先使用可用的 fontconfig，否则查询用户/系统 Windows 字体注册表。缺少 Noto 字体仍是出版依赖问题；产品不会自动安装字体或修改全局配置。

任务 argv 使用 Windows 路径，含空格的路径需正确引用。参数含 shell 特殊字符时优先使用原生 `.exe`；`.cmd`/`.bat` 启动器仍遵循 Windows 批处理引用规则。PowerShell 内置命令不是独立可执行程序；需要时提交明确的 `powershell.exe` 或 `pwsh.exe` 调用。产品不会自动翻译 `sleep` 等 POSIX 命令；跨平台延时可用所选 Python 解释器（`python -c "import time; time.sleep(1)"`）。

```powershell
rtk uv run mmagent doctor
# 仅在开始新题时执行；目录放在产品仓库之外。
rtk uv run mmagent init 'D:\MathModelCases\case-one'
```

Linux 专有的 runtime 机制由本机文件锁和 Job Object 替代，详见[runtime](modules/runtime.md)。选定输入树和发布 staging 会拒绝符号链接及 Windows junction。创建符号链接可能要求开发者模式或管理员权限，正常使用产品不要求开启它们。跨系统恢复时若不能保留原绝对路径，仍需显式导入新 case。

## 配置新 case

使用发布仓库之外的独立 case 目录：

```text
rtk uv run mmagent init CASE_DIR
rtk uv run mmagent doctor CASE_DIR
```

对照 `config/case.example.toml` 检查 `CASE_DIR/case.toml`。当前顶层配置为 runtime、policy、profiles、tools；不支持的键会报错。示例和初始化器含历史模型名 `gpt-5.6-terra`、`gpt-5.6-luna`、`gpt-5.6-sol`，不保证新账号可用。开始受管工作前明确设定实际可用的 model/effort。case profile 名选择设置；如使用 `codex_profile`，它指向已经存在的用户级 profile。研究档位是人工选择，不是自动发现模型或强制硬预算。

示例/初始化器的网络访问默认 false。不要为补工具或认证静默启用网络；重要授权/权限变化要说明并确认。`doctor` 只做诊断，不批准研究。使用现有人工档位/回答/决定流程；`start` 校验批准的题面哈希与 profile model/effort。model/effort 或题面改变时，需要新的真实决定。

PDF 导入通过 `pypdf` 读取内嵌文本；扫描 PDF 可在外部使用 OCR/MinerU 预处理，并保留原件。产品没有内置 MinerU SDK。XLSX 使用 `openpyxl` 导入，不计算公式。预处理服务 token 不得进入 case 文件。

## 恢复现有建模 case

Git 能独立于旧 session 恢复产品源码、测试与文档。个人 case 需要另行做一致备份：先停止 supervisor/写入方，保存完整 case，包括隐藏 `.runtime` 的 SQLite 状态及存在的 WAL/SHM 文件、回执、任务输入/工作目录/attempt 日志、产物、人工记录、题面/数据/来源/证据 freeze、比较、request、配置、论文和构建文件。另存外部原件和导出包。单靠 SQLite 重建 case 会丢失必要材料。

Runtime 记录保存绝对 workspace 与 events/stderr 路径，策略快照可能包含绝对 extra write paths。应在原绝对路径恢复 case。当前没有 rebase CLI；改变位置不代表完成经过验证的 runtime 迁移。原路径不可用时，保留旧 case 作证据，初始化新 case 并显式导入所需材料。决定和 ArtifactRef 不会自动转移；不得手改数据库来掩盖限制。

已保存的 provider session ID 不等于对话本身。`resume` 和 workflow polling 需要原 session 仍可由当前 provider/client 访问。历史丢失时保留旧 task/attempt/日志/输出，用新 ID/session 的新任务显式接续选中的材料；不要删除旧记录或伪造。原地替换 session 和依赖重新分配尚未实现。完整步骤、状态拥有者、schema 和新会话提示词见[开发交接](dev.md)，日常操作见[使用说明](guide.md)和[命令参考](cli.md)。
