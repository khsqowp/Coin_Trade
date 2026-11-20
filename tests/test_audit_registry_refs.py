import json

from scripts.research.audit_registry_refs import audit


def test_registry_reference_audit_resolves_documents_and_annotated_artifacts(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs/result.md").write_text("result", encoding="utf-8")
    (tmp_path / "scripts/probe.py").write_text("pass", encoding="utf-8")
    (tmp_path / "docs/research").mkdir()
    rows = [
        {"id": 1, "verdict": "REJECT", "doc_ref": "docs/result.md",
         "artifacts": ["scripts/probe.py --variant 2"]},
        {"id": 2, "verdict": "BLOCKED", "doc_ref": "docs/missing.md", "artifacts": []},
    ]
    registry = tmp_path / "docs/research/registry.jsonl"
    registry.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = audit(tmp_path)

    assert result["rows"] == 2
    assert result["doc_refs_resolved"] == 1
    assert result["missing_doc_refs"] == [2]
    assert result["rows_without_artifacts"] == [2]
    assert result["missing_artifact_refs"] == []
