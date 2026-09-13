import json

from mathmodel_agent.evidence import (
    affected_references,
    bibliography_for_freeze,
    curate_batch,
    freeze_evidence,
    pin_consumer,
    register_claim,
    register_source,
    report_error,
    write_source_notes,
    write_topic,
)


def test_sources_are_versioned_deduplicated_by_identity_not_title_and_freeze_is_scoped(tmp_path):
    case = tmp_path / "case"
    source = register_source(
        case,
        "A shared title",
        text="full text version one",
        doi="10.1234/example",
        citation={"author": "Li", "year": 2026, "entry_type": "article", "journal": "Test Journal"},
    )
    same = register_source(case, "Renamed", text="full text version two", doi="https://doi.org/10.1234/example")
    distinct = register_source(case, "A shared title", text="a different source")
    assert same["source_id"] == source["source_id"]
    assert len(same["versions"]) == 2
    assert distinct["source_id"] != source["source_id"]
    old_document = case / source["versions"][0]["document"]
    assert old_document.read_text() == "full text version one"

    write_source_notes(case, source["source_id"], "Faithful text is stored separately.", limitations="The initial source is abstract-only.")
    claim = register_claim(case, "The method has a stated limit.", evidence_kind="source", evidence_id=source["source_id"], locator="section 2", scope="Only the studied setting")
    pin_consumer(case, "paper", source_ids=[source["source_id"]], claim_ids=[claim["claim_id"]])
    topic = write_topic(case, "method limit", "Navigation summary", source_ids=[source["source_id"]], claim_ids=[claim["claim_id"]])
    assert "not evidence" in topic.read_text()

    freeze = freeze_evidence(case, "adopted", consumer_id="paper")
    bib = bibliography_for_freeze(case, "adopted")
    assert source["citekey"] in bib.read_text()

    unrelated = register_source(case, "New unrelated work", text="new information")
    assert json.loads((case / "freezes" / "adopted.json").read_text())["status"] == "ready"
    assert unrelated["source_id"] not in [item["id"] for item in freeze["sources"]]

    error = report_error(case, "source", source["source_id"], "The quoted unit is wrong.")
    assert claim["claim_id"] in error["affected"]["claims"]
    assert affected_references(case, "source", source["source_id"])["freezes"] == ["adopted"]
    assert json.loads((case / "freezes" / "adopted.json").read_text())["status"] == "needs_review"


def test_batch_curation_is_additive(tmp_path):
    batch = curate_batch(
        tmp_path / "case",
        "search-1",
        [{"title": "First", "text": "one"}, {"title": "Second", "text": "two"}],
    )
    assert len(batch["source_ids"]) == 2
