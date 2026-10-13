"""Explicit dry-run-first cleanup. Never delete the current published revision."""

import json
import os
import re
import shutil
import stat
import time
from pathlib import Path

from filelock import FileLock


def linked(path):
    """Reject symlinks and Windows reparse points, including junctions."""
    return path.is_symlink() or bool(
        getattr(os.lstat(path), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def validate_policy(keep, older_than_days, apply):
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise ValueError("keep must be a positive integer")
    if (
        isinstance(older_than_days, bool)
        or not isinstance(older_than_days, int)
        or older_than_days < 0
    ):
        raise ValueError("older_than_days must be a nonnegative integer")
    if not isinstance(apply, bool):
        raise ValueError("apply must be a boolean")
    return time.time() - older_than_days * 86400


def safe_tree(target, root):
    resolved = target.resolve()
    if resolved == root.resolve() or not resolved.is_relative_to(root.resolve()) or linked(target):
        raise ValueError("Cleanup target escapes root or is linked")
    # Walk without following directory links, validating before descent.
    children = []
    for parent, directories, files in os.walk(target, followlinks=False):
        for name in directories + files:
            child = Path(parent) / name
            if linked(child) or not child.resolve().is_relative_to(resolved):
                raise ValueError("Cleanup refuses linked output trees")
            children.append(child)
    return children


def cleanup_job(pipeline, job_id, keep=3, older_than_days=30, apply=False):
    cutoff = validate_policy(keep, older_than_days, apply)
    pipeline.get_job(job_id)
    job = pipeline.root / job_id
    if job.resolve().parent != pipeline.root.resolve() or linked(job):
        raise ValueError("Cleanup refuses linked job directories")
    with FileLock(job / ".lock", timeout=10):
        saved = pipeline.get_job(job_id)
        manifest = saved["manifest"]
        revisions = sorted(
            [p for p in job.iterdir() if p.is_dir() and re.fullmatch(r"[0-9a-f]{32}", p.name)],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        protected = {manifest["revision"], *(p.name for p in revisions[:keep])}
        references = []
        # Keep revisions referenced by any manifest artifact field as well.
        for value in manifest.values():
            for path in value if isinstance(value, list) else [value]:
                if isinstance(path, str):
                    reference = Path(path).resolve()
                    references.append(reference)
                    for revision in revisions:
                        if reference.is_relative_to(revision.resolve()):
                            protected.add(revision.name)
        candidates = [
            p for p in revisions if p.name not in protected and p.stat().st_mtime <= cutoff
        ]
        current = job / manifest["revision"]
        if linked(current):
            raise ValueError("Cleanup refuses linked revision directories")
        for kind in ("previews", "reviews"):
            # Older manifests do not identify the Office snapshot retained in quality.
            # Keep previews conservatively rather than remove its supporting images.
            if kind == "previews" and saved["quality"].get("office_layout"):
                continue
            snapshot_root = current / kind
            if not snapshot_root.exists():
                continue
            if linked(snapshot_root):
                raise ValueError("Cleanup refuses linked snapshot directories")
            snapshots = sorted(
                [
                    p
                    for p in snapshot_root.iterdir()
                    if p.is_dir() and re.fullmatch(r"[0-9a-f]{32}", p.name)
                ],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for snapshot in snapshots[keep:]:
                if any(reference.is_relative_to(snapshot.resolve()) for reference in references):
                    continue
                children = safe_tree(snapshot, job)
                if max(p.stat().st_mtime for p in [snapshot, *children]) <= cutoff:
                    candidates.append(snapshot)
        repair_root = job / "repair-candidates"
        if repair_root.is_dir():
            if linked(repair_root):
                raise ValueError("Cleanup refuses linked repair directories")
            for candidate in repair_root.iterdir():
                if not candidate.is_dir() or not re.fullmatch(r"[0-9a-f]{32}", candidate.name):
                    continue
                children = safe_tree(candidate, job)
                terminal = (candidate / "promoted.json").is_file()
                for trace_path in candidate.glob("*/repair.json"):
                    terminal |= json.loads(trace_path.read_text(encoding="utf-8")).get(
                        "status"
                    ) in {"failed", "rejected"}
                if terminal and max(p.stat().st_mtime for p in [candidate, *children]) <= cutoff:
                    candidates.append(candidate)
        selected = []
        for target in candidates:
            # Verify absolute paths and every child before recursive deletion on Windows.
            children = safe_tree(target, job)
            resolved = target.resolve()
            selected.append(
                {
                    "path": str(resolved),
                    "kind": target.parent.name
                    if target.parent.name in {"previews", "reviews", "repair-candidates"}
                    else "revision",
                    "bytes": sum(p.stat().st_size for p in children if p.is_file()),
                }
            )
        if apply:
            for target in selected:
                shutil.rmtree(target["path"])
        return {
            "success": True,
            "dry_run": not apply,
            "job_id": job_id,
            "protected_revision": manifest["revision"],
            "selected": selected,
            "bytes": sum(target["bytes"] for target in selected),
        }
