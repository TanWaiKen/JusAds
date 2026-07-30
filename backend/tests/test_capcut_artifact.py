from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from jusads_compliance.capcut_artifact import CapCutArtifactError, build_capcut_editing_package


def _draft(root: Path, task_id: str) -> dict[str, str]:
    project = root / "draft-one"
    project.mkdir()
    (project / "draft_content.json").write_text(json.dumps({"draft": True}), encoding="utf-8")
    (project / "draft_meta_info.json").write_text("{}", encoding="utf-8")
    media = root / "media" / task_id
    media.mkdir(parents=True)
    (media / "01_safe.mp4").write_bytes(b"safe-scene")
    return {"draft_folder": str(root), "draft_name": "draft-one"}


def test_builds_package_with_project_media_and_instructions(tmp_path: Path) -> None:
    package = build_capcut_editing_package(_draft(tmp_path, "task-1"), task_id="task-1")

    assert package is not None
    with zipfile.ZipFile(package["archive_path"]) as archive:
        assert sorted(archive.namelist()) == [
            "README.txt",
            "capcut_draft/draft_content.json",
            "capcut_draft/draft_meta_info.json",
            "media/01_safe.mp4",
        ]
        assert "relink" in archive.read("README.txt").decode("utf-8").lower()
    Path(package["archive_path"]).unlink()


def test_does_not_package_warning_only_fallback(tmp_path: Path) -> None:
    assert build_capcut_editing_package({"warning": "library unavailable"}, task_id="task-1") is None


def test_rejects_draft_outside_the_declared_root(tmp_path: Path) -> None:
    with pytest.raises(CapCutArtifactError):
        build_capcut_editing_package(
            {"draft_folder": str(tmp_path), "draft_name": "../outside"}, task_id="task-1"
        )
