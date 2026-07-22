from __future__ import annotations

from pathlib import Path

from scripts.build_reproducibility_manifest import build_manifest, verify_manifest


def test_manifest_detects_content_change(tmp_path: Path) -> None:
    file = tmp_path / "value.txt"
    file.write_text("a", encoding="utf-8")
    manifest = build_manifest(tmp_path, [file])

    assert verify_manifest(tmp_path, manifest) == []
    file.write_text("b", encoding="utf-8")
    assert verify_manifest(tmp_path, manifest) == ["value.txt"]
