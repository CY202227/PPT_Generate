"""Explicit dry-run-first cleanup. Never delete the current published revision."""

import json
import re
import shutil
import time

from filelock import FileLock


def cleanup_job(pipeline, job_id, keep=3, older_than_days=30, apply=False):
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise ValueError("keep must be a positive integer")
    if (
        isinstance(older_than_days, bool)
        or not isinstance(older_than_days, int)
        or older_than_days < 0
    ):
        raise ValueError("older_than_days must be a nonnegative integer")
    pipeline.get_job(job_id)
    job = pipeline.root / job_id
    if job.resolve().parent != pipeline.root.resolve() or job.is_symlink():
        raise ValueError("Cleanup refuses linked job directories")
    if not isinstance(apply, bool):
        raise ValueError("apply must be a boolean")
    cutoff = time.time() - older_than_days * 86400
    with FileLock(job / ".lock", timeout=10):
        manifest = pipeline.get_job(job_id)["manifest"]
        revisions = sorted(
            [p for p in job.iterdir() if p.is_dir() and re.fullmatch(r"[0-9a-f]{32}", p.name)],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        protected = {manifest["revision"], *(p.name for p in revisions[:keep])}
        # Keep revisions referenced by any manifest artifact field as well.
        for value in manifest.values():
            for path in value if isinstance(value, list) else [value]:
                if isinstance(path, str):
                    for revision in revisions:
                        if path.startswith(str(revision) + "/") or path.startswith(
                            str(revision) + "\\"
                        ):
                            protected.add(revision.name)
        candidates = [
            p for p in revisions if p.name not in protected and p.stat().st_mtime <= cutoff
        ]
        repair_root = job / "repair-candidates"
        if repair_root.is_dir():
            for candidate in repair_root.iterdir():
                if not candidate.is_dir() or not re.fullmatch(r"[0-9a-f]{32}", candidate.name):
                    continue
                terminal = (candidate / "promoted.json").is_file()
                for trace_path in candidate.glob("*/repair.json"):
                    terminal |= json.loads(trace_path.read_text(encoding="utf-8")).get(
                        "status"
                    ) in {"failed", "rejected"}
                if (
                    terminal
                    and max(p.stat().st_mtime for p in [candidate, *candidate.rglob("*")]) <= cutoff
                ):
                    candidates.append(candidate)
        selected = []
        for target in candidates:
            # Verify absolute paths and every child before recursive deletion on Windows.
            resolved = target.resolve()
            if resolved == job.resolve() or not resolved.is_relative_to(job.resolve()):
                raise ValueError("Cleanup target escapes job directory")
            children = list(target.rglob("*"))
            if target.is_symlink() or any(
                p.is_symlink() or not p.resolve().is_relative_to(resolved) for p in children
            ):
                raise ValueError("Cleanup refuses linked output trees")
            selected.append(
                {
                    "path": str(resolved),
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
