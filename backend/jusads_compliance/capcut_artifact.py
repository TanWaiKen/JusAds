"""Portable, auditable delivery packages for CapCut remediation drafts.

The CapCut libraries create a desktop draft that refers to local media paths.
Those paths are meaningful only on the worker machine, so the user-facing
artifact must include both the draft files and every source segment.  CapCut
may ask the editor to relink the packaged ``media`` directory after extraction;
we state that requirement explicitly instead of claiming a cloud ZIP opens by
itself.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
import zipfile


class CapCutArtifactError(ValueError):
    """The local draft cannot be safely delivered as an editing package."""


def _safe_draft_name(value: object) -> str:
    name = str(value or "").strip()
    if not name or Path(name).name != name or name in {".", ".."}:
        raise CapCutArtifactError("CapCut draft name is invalid")
    return name


def build_capcut_editing_package(
    draft: Mapping[str, Any] | None,
    *,
    task_id: str,
) -> dict[str, Any] | None:
    """Create a ZIP containing a generated CapCut draft and its media.

    ``None`` means the optional CapCut library did not produce a draft.  It is
    intentionally different from a failure: MP4 remediation and rechecking can
    still complete without an editable package.
    """

    if not isinstance(draft, Mapping) or draft.get("warning"):
        return None
    draft_root = Path(str(draft.get("draft_folder") or "")).resolve()
    draft_name = _safe_draft_name(draft.get("draft_name"))
    project_dir = (draft_root / draft_name).resolve()
    media_dir = (draft_root / "media" / task_id).resolve()
    if project_dir.parent != draft_root or not project_dir.is_dir():
        raise CapCutArtifactError("CapCut draft project was not created")
    if not (project_dir / "draft_content.json").is_file() or not (project_dir / "draft_meta_info.json").is_file():
        raise CapCutArtifactError("CapCut draft project is incomplete")
    if media_dir.parent.parent != draft_root or not media_dir.is_dir():
        raise CapCutArtifactError("CapCut draft media is unavailable")

    fd, archive_path = tempfile.mkstemp(prefix=f"capcut_{task_id}_", suffix=".zip")
    os.close(fd)
    archive = Path(archive_path)
    readme = (
        "JusAds compliance remediation editing package\n\n"
        "This ZIP contains the generated CapCut project and the exact safe and "
        "AI-edited scene clips used to render the remediated video.\n\n"
        "1. Extract all files.\n"
        "2. Copy the project folder into the CapCut Desktop draft location.\n"
        "3. Open CapCut. If prompted for missing media, relink it to the extracted media folder.\n"
        "4. Any manual edits create a new version and must be rechecked before publishing.\n"
    )
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for source, arc_root in ((project_dir, "capcut_draft"), (media_dir, "media")):
                for path in sorted(source.rglob("*")):
                    # Do not follow or package links from a worker's temporary area.
                    if not path.is_file() or path.is_symlink():
                        continue
                    bundle.write(path, Path(arc_root, path.relative_to(source)).as_posix())
            bundle.writestr("README.txt", readme)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        return {
            "archive_path": str(archive),
            "file_name": f"{draft_name}_editing_package.zip",
            "sha256": digest,
            "size_bytes": archive.stat().st_size,
            "format": "capcut_editing_package",
            "relink_media_if_prompted": True,
        }
    except Exception:
        archive.unlink(missing_ok=True)
        raise
