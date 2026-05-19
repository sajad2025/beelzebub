#!/usr/bin/env python3
"""
build_manifest.py

After extract_pdf.py has produced per-chapter JSON in data/, this builds:

  MANIFEST.json    -- counts, source provenance, schema version
  CHECKSUMS.sha256 -- SHA-256 of every file under data/ and the source PDF

Also runs JSON Schema validation against schema/v1.json if jsonschema is
installed (it's listed in scripts/requirements.txt).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def validate_schema(data_files: list[Path], schema_path: Path) -> tuple[int, list[str]]:
    """Returns (validated_count, errors). If jsonschema isn't installed, returns (0, [])."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        print("  (jsonschema not installed; skipping schema validation)", flush=True)
        return 0, []
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    validated = 0
    errors: list[str] = []
    for p in data_files:
        if p.suffix != ".json":
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        errs = sorted(validator.iter_errors(doc), key=lambda e: e.path)
        if errs:
            errors.extend(f"{p}: {e.message}" for e in errs)
        else:
            validated += 1
    return validated, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--pdf", type=Path, default=Path("Beelzebubs_Tales.pdf"))
    ap.add_argument("--schema", type=Path, default=Path("schema/v1.json"))
    args = ap.parse_args()

    data_files = walk_files(args.data)
    json_files = [p for p in data_files if p.suffix == ".json"]

    chapters = []
    total_paragraphs = 0
    total_pages: set[tuple[int, int]] = set()
    for p in sorted(json_files):
        if p.name == "front-matter.json":
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        n_para = len(doc["paragraphs"])
        total_paragraphs += n_para
        for para in doc["paragraphs"]:
            for pg in range(para["page_start"], para["page_end"] + 1):
                total_pages.add((doc["number"], pg))
        chapters.append(
            {
                "number": doc["number"],
                "title": doc["title"],
                "page_start": doc["page_start"],
                "page_end": doc["page_end"],
                "paragraphs": n_para,
                "file": str(p),
            }
        )

    front_matter_paragraphs = 0
    fm_path = args.data / "front-matter.json"
    if fm_path.exists():
        front_matter_paragraphs = len(
            json.loads(fm_path.read_text(encoding="utf-8"))["paragraphs"]
        )

    manifest = {
        "schema_version": 1,
        "snapshot_id": os.environ.get(
            "GITHUB_RUN_ID",
            datetime.now(timezone.utc).strftime("local-%Y%m%dT%H%M%SZ"),
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "git_sha": os.environ.get("GITHUB_SHA", ""),
        "source": {
            "pdf": args.pdf.name,
            "pdf_sha256": sha256_file(args.pdf) if args.pdf.exists() else None,
            "edition": (
                "joshuatilton typesetting via Vellum (2019), original text "
                "G. I. Gurdjieff, All and Everything First Series, 1950."
            ),
        },
        "license": {
            "code": "MIT",
            "data": "Public domain (text); typesetting attribution as above",
            "attribution": (
                "G. I. Gurdjieff, Beelzebub's Tales to His Grandson "
                "(All and Everything First Series). Text in the public domain. "
                "Typeset by joshuatilton via Vellum, 2019."
            ),
        },
        "counts": {
            "chapters": len(chapters),
            "chapter_paragraphs": total_paragraphs,
            "front_matter_paragraphs": front_matter_paragraphs,
            "distinct_pages": len(total_pages),
            "data_files": len(data_files),
        },
        "chapters": chapters,
    }

    manifest_path = Path("MANIFEST.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {manifest_path}")

    # SHA-256 of every data file and the source PDF.
    checksum_path = Path("CHECKSUMS.sha256")
    files_to_hash = list(data_files)
    if args.pdf.exists():
        files_to_hash.append(args.pdf)
    with checksum_path.open("w", encoding="utf-8") as f:
        for p in files_to_hash:
            try:
                digest = sha256_file(p)
            except OSError as e:
                print(f"  ! could not hash {p}: {e}")
                continue
            f.write(f"{digest}  {p}\n")
    print(f"Wrote {checksum_path} ({len(files_to_hash)} files)")

    # Optional schema validation.
    if args.schema.exists():
        validated, errors = validate_schema(json_files, args.schema)
        if errors:
            print(f"  SCHEMA VALIDATION FAILED: {len(errors)} errors", file=sys.stderr)
            for e in errors[:10]:
                print(f"    {e}", file=sys.stderr)
            return 1
        if validated:
            print(f"  Schema validation: {validated} files passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
