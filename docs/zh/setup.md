# 环境配置

在产品根目录运行：

```text
uv sync --locked
uv run mmagent doctor
```

Python 依赖由 `uv` 和 `uv.lock` 管理；可选的 Node 工具使用 `bun`，日常 shell 命令使用 `rtk`。`doctor` 会检查 Codex、uv、bun、rtk、XeLaTeX/latexmk/BibTeX、CTeX/xeCJK/zhnumber、CJK 字体、Poppler 和 case 工具。

PDF 导入使用 `pypdf`，XLSX 导入使用 `openpyxl`。扫描 PDF 请先在外部使用 OCR 或 MinerU 预处理，并保留原文件。本版本没有内置 MinerU 适配器。Provider 凭据和模型档位保存在用户的 Codex 配置中；case TOML 不保存密钥。示例见 `config/case.example.toml`。

