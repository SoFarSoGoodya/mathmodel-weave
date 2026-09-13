# 证据

`mathmodel_agent.evidence` 将 case 证据保存为普通可读文件，不发布 bundle，也不维护运行状态。需要正式产物时，由调用方暂存选定文件并调用 `mathmodel_agent.runtime.artifacts.publish_bundle`。

## 导入

```python
from mathmodel_agent.evidence import intake_pdf, correct_pdf_text, request_visual_review

problem = intake_pdf("/cases/A", "/cases/A/incoming/problem.pdf", problem_id="problem")
correct_pdf_text("/cases/A", "problem", "<!-- page: 1 -->\n\nReviewed wording")
request_visual_review("/cases/A", "problem", 1, "table heading", "Confirm the unit.")
```

原 PDF 复制到 `problem/raw/`，抽取结果是带页码标记的 Markdown；修正另存为 Markdown 和 unified diff。视觉请求必须指定一个页面和区域，因此只检查局部。

```python
from mathmodel_agent.evidence import intake_xlsx, validate_xlsx_export

profile = intake_xlsx("/cases/A", "/cases/A/incoming/data.xlsx", dataset_id="data")
assert validate_xlsx_export("/cases/A", "data")["ok"]
```

XLSX 导入会复制原文件到 `datasets/raw/`，读取包括隐藏表在内的所有工作表，为每个有效矩形区域写 CSV，并记录预览、边界、类型统计、公式/缓存风险和 profile。它会进行第二次源扫描，比对每个 CSV 值和区域尺寸；不会清洗、填补、去重或改变单位。`pypdf` 不做扫描 PDF OCR，`openpyxl` 不计算公式；缺少缓存的公式保留为公式文本，并记录为 `formula_without_cache`，不会转成零。

OCR 或 MinerU 可以在外部预处理。本版本没有内置 MinerU SDK，内置路径仍是 `pypdf` 和 `openpyxl`。外部 token 只能放在用户本机环境中，不得写入 Git、case、Markdown、JSON 或聊天。

## 来源、主张与固定版本

```python
from mathmodel_agent.evidence import register_source, register_claim, pin_consumer

source = register_source(
    "/cases/A", "Official rule", text="Faithful accessible text",
    canonical_url="https://example.org/rule", access_scope="full_text",
    citation={"author": "Organizer", "year": 2026},
)
claim = register_claim(
    "/cases/A", "The rule applies to this submission.",
    evidence_kind="source", evidence_id=source["source_id"], locator="section 3",
    scope="Current competition year",
)
pin_consumer("/cases/A", "paper", source_ids=[source["source_id"]], claim_ids=[claim["claim_id"]])
```

`document.md` 是忠实内容，`sources/notes/<source>.md` 明确记录摘要、用途和限制。摘要不能支持全文主张，应使用 `access_scope="abstract"` 等真实范围。来源身份使用 DOI、规范 URL 或内容哈希；仅标题相同不会合并来源。文档变化会形成新的保留版本。`write_topic` 只负责导航，不替代引用。`curate_batch` 用于追加搜索结果；消费者会继续使用已 pin 的版本，直到明确调用 `refresh_consumer`。

## 冻结与修正

```python
from mathmodel_agent.evidence import freeze_evidence, bibliography_for_freeze, report_error

freeze_evidence("/cases/A", "paper-v1", consumer_id="paper", rules_source_ids=[source["source_id"]])
bibliography_for_freeze("/cases/A", "paper-v1")
report_error("/cases/A", "source", source["source_id"], "The quoted unit is incorrect.")
```

冻结记录采用的来源/数据版本哈希、带定位的主张、结果引用、题目引用和规则来源；BibTeX 只包含冻结来源。报告错误只会将相关主张、consumer pin 和冻结标为 `needs_review`，旧版本仍可复现。

CLI 在 `mmagent evidence` 下提供导入、校验、修正文本、来源/笔记、pin/refresh/freeze 和 bibliography 命令；没有独立 evidence daemon 或状态数据库。

