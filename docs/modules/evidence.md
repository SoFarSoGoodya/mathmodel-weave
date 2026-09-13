# Evidence

`mathmodel_agent.evidence` keeps case evidence as ordinary, readable files. It does not
publish bundles or maintain runtime state. A caller stages selected files and invokes
`mathmodel_agent.runtime.artifacts.publish_bundle` when it needs a formal artifact.

## Intake

```python
from mathmodel_agent.evidence import intake_pdf, correct_pdf_text, request_visual_review

problem = intake_pdf("/cases/A", "/cases/A/incoming/problem.pdf", problem_id="problem")
correct_pdf_text("/cases/A", "problem", "<!-- page: 1 -->\n\nReviewed wording")
request_visual_review("/cases/A", "problem", 1, "table heading", "Confirm the unit.")
```

The original is copied to `problem/raw/`; extraction is page-marked Markdown. Corrections
are separate Markdown plus a unified diff. A visual request always names one page and one
region, so it is a review request rather than a whole-document vision task.

```python
from mathmodel_agent.evidence import intake_xlsx, validate_xlsx_export

profile = intake_xlsx("/cases/A", "/cases/A/incoming/data.xlsx", dataset_id="data")
assert validate_xlsx_export("/cases/A", "data")["ok"]
```

XLSX intake copies the original to `datasets/raw/`, streams every sheet including hidden
sheets, writes one CSV per effective rectangular region, and records a bounded preview,
per-sheet bounds, schema/type counts, formula/cache risks, and a profile. It performs a
second source scan and compares every exported CSV value and region dimension. It never
cleans, fills, deduplicates, or changes units: those operations require a separately named
derived dataset.

`pypdf` extracts embedded text but does not OCR scanned pages. `openpyxl` can read formula
text and any stored cache but does not calculate formulas. An absent cache remains a formula
literal in the CSV and is recorded as `formula_without_cache`, never converted to zero.

Document and literature parsing may be preprocessed externally with OCR or MinerU when needed.
This release has no in-product MinerU SDK adapter; the built-in path uses `pypdf` and `openpyxl`.
Any external service token belongs only in the user's local environment and must never be stored
in Git, a case, Markdown, JSON, or chat. XLSX remains on the deterministic `openpyxl` intake and
validation path.

## Sources, claims, and pins

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

`document.md` is faithful content, while `sources/notes/<source>.md` is explicitly a
summary/use/limits note. Use `access_scope="abstract"` or another truthful scope for
metadata or abstracts: they cannot support a full-text claim. Source identity uses DOI,
canonical URL, or content hash; a matching title alone does not merge sources. A changed
document under an existing identity becomes a new retained version. `write_topic` creates
navigation only, never a citation substitute.

Use `curate_batch` for additive search results. Consumers retain the exact current versions
they pinned until `refresh_consumer` is explicitly called.

## Freeze and correction

```python
from mathmodel_agent.evidence import freeze_evidence, bibliography_for_freeze, report_error

freeze_evidence("/cases/A", "paper-v1", consumer_id="paper", rules_source_ids=[source["source_id"]])
bibliography_for_freeze("/cases/A", "paper-v1")
report_error("/cases/A", "source", source["source_id"], "The quoted unit is incorrect.")
```

A freeze records adopted source/dataset version hashes, claims with locators, result refs,
problem reference, and applicable rules sources. Its BibTeX contains only adopted frozen
sources and stable citekeys. New unrelated sources do not alter a freeze. A reported source
or dataset error marks only dependent claims, consumer pins, and freezes `needs_review`;
the original freeze and old source version remain reproducible.

## Optional CLI hook

The product CLI registers PDF/XLSX intake and validation, corrected PDF text, source/notes,
pin/refresh/freeze, and bibliography subcommands under `mmagent evidence`. There is no
separate evidence daemon or state database.
