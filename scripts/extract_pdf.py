#!/usr/bin/env python3
"""
extract_pdf.py

Walks Beelzebubs_Tales.pdf and produces per-chapter JSON files under data/.

The source PDF (joshuatilton/Vellum 2019 typesetting of Gurdjieff's text)
places a small chapter.page anchor before every paragraph in the form
    1.4        -> chapter 1, original-hard-copy page 4
    1.5-6      -> chapter 1, paragraph spans pages 5 and 6
    48.1210-1  -> chapter 48, pages 1210-1211 (trailing-digit abbreviation)

The first paragraph of each chapter (drop-cap opener) is unanchored in the
print; we synthesize an anchor for it by inferring its end page as
(first explicit anchor page - 1).

Front matter (pages before chapter 1) has no chapter.page anchors --
paragraphs are separated by a Vellum ornament glyph that pdftotext extracts
as a bare "2". We emit it as data/front-matter.json with simple sequential
anchors fa.1, fa.2, ...

Pipeline:
  1. Shell out to `pdftotext -layout` on the source PDF.
  2. Walk the text line by line, stripping running headers/footers.
  3. Detect chapter title pages by the centered "<number>" + all-caps title.
  4. Group lines under anchor markers into paragraphs.
  5. Write data/ch01.json ... data/ch48.json + data/front-matter.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ANCHOR_RE = re.compile(r"^\s*(\d+)\.(\d+)(?:-(\d+))?\s*$")
CHAPTER_HEADING_RE = re.compile(r"^\s+(\d{1,2})\s*$")  # centered "  1", "  48"
RUNNING_LINE_RE = re.compile(
    r"""
    ^\s*
    (?:
        # "<page-num> | A L L A N D E V E RY T H I N G..." -- spaced-cap book title
        \d+\s*\|\s*[A-Z](?:\s+[A-Z])+ |
        # "<chapter title> | <page-num>" -- recto running head. The title may
        # contain quotes (“ ”), an ellipsis (…, used when a long title is
        # truncated in the running head), commas, colons, etc., so accept any
        # run of non-pipe characters before the page number rather than an
        # enumerated character class (every "|" in this corpus is a header).
        [A-Za-z][^|]*?\|\s*\d+ |
        # "<roman-numeral> | <title>"
        [ivxlcdm]+\s*\|\s*[A-Za-z]
    )
    .*$
    """,
    re.VERBOSE,
)
DROP_CAP_RE = re.compile(r"^([A-Z]) ([a-z])")  # post-collapse: 'A mong' -> 'Among'
SOFT_HYPHEN_RE = re.compile(r"(?<=[a-z])- (?=[a-z])")  # 'under- standing' -> 'understanding'

# Typographic ligatures (Unicode FB00-FB04 block) -> plain ASCII pairs.
# We keep curly quotes, em/en dashes, and other meaningful punctuation as-is.
LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "ft",
    "ﬆ": "st",
}
LIGATURE_RE = re.compile("|".join(map(re.escape, LIGATURES)))


def looks_like_all_caps_title(line: str) -> bool:
    """A centered all-caps title line (allowing punctuation, digits, quotes)."""
    stripped = line.strip()
    if len(stripped) < 3:
        return False
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    # Allow up to one lowercase letter (covers names, edge cases)
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) >= 0.9 and len(stripped) <= 80


def is_running_line(line: str) -> bool:
    """Detect page-header/footer lines that should be stripped."""
    if "|" not in line:
        return False
    if RUNNING_LINE_RE.match(line):
        return True
    # Conservative fallback for the noisy spaced-caps variant
    return "A L L A N D E V E RY T H I N G" in line


def parse_anchor(line: str) -> tuple[int, int, int] | None:
    """Return (chapter, page_start, page_end) for a paragraph anchor line."""
    m = ANCHOR_RE.match(line)
    if not m:
        return None
    chapter = int(m.group(1))
    start = int(m.group(2))
    end_suffix = m.group(3)
    if end_suffix is None:
        return chapter, start, start
    # Trailing-digit abbreviation: replace last len(end_suffix) digits of start.
    suffix_len = len(end_suffix)
    keep = (start // (10 ** suffix_len)) * (10 ** suffix_len)
    end = keep + int(end_suffix)
    # Defensive: if the abbreviation rolls under (e.g., "1.9-0" meaning 9-10
    # would compute to 0 -- but we'd see "9-10" written out in practice),
    # bump by a power of ten until end > start.
    while end <= start:
        end += 10 ** suffix_len
    return chapter, start, end


def fix_dropcap(text: str) -> str:
    """Collapse 'A      mong' (drop-cap artifact) into 'Among'."""
    return DROP_CAP_RE.sub(r"\1\2", text, count=1)


def collapse_ws(text: str) -> str:
    """Join wrapped lines into one logical paragraph."""
    text = LIGATURE_RE.sub(lambda m: LIGATURES[m.group(0)], text)
    text = re.sub(r"\s+", " ", text).strip()
    # End-of-line hyphenation collapses 'under- standing' -> 'understanding'.
    # Intentional compounds like 'wholly-manifested-intonation' have no space
    # around the hyphens, so they're unaffected.
    text = SOFT_HYPHEN_RE.sub("", text)
    return text


@dataclass
class Paragraph:
    anchor: str
    chapter: int
    page_start: int
    page_end: int
    text: str


@dataclass
class Chapter:
    number: int
    title: str
    paragraphs: list[Paragraph] = field(default_factory=list)


def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def run_pdftotext(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ----- main parse loop -------------------------------------------------------


def parse(text: str) -> tuple[list[Chapter], list[Paragraph]]:
    """Returns (chapters, front_matter_paragraphs)."""
    lines = text.splitlines()

    chapters: list[Chapter] = []
    front_matter_paragraphs: list[Paragraph] = []
    current: Chapter | None = None
    pending_text: list[str] = []
    pending_anchor: tuple[int, int, int] | None = None
    # For pre-chapter (front matter) accumulation.
    front_buf: list[str] = []
    front_count = 0

    def flush_paragraph():
        nonlocal pending_text, pending_anchor
        if not pending_text:
            pending_anchor = None
            return
        joined = collapse_ws(" ".join(pending_text))
        joined = fix_dropcap(joined)
        if not joined:
            pending_text = []
            pending_anchor = None
            return
        if current is not None and pending_anchor is not None:
            ch, ps, pe = pending_anchor
            current.paragraphs.append(
                Paragraph(
                    anchor=_anchor_str(ch, ps, pe),
                    chapter=ch,
                    page_start=ps,
                    page_end=pe,
                    text=joined,
                )
            )
        elif current is not None and pending_anchor is None:
            # Chapter opener (drop-cap paragraph, no explicit anchor in print).
            # We anchor it provisionally to chapter.1; end page is patched after
            # we see the next explicit anchor.
            current.paragraphs.append(
                Paragraph(
                    anchor=f"{current.number}.1",
                    chapter=current.number,
                    page_start=1,
                    page_end=1,
                    text=joined,
                )
            )
        pending_text = []
        pending_anchor = None

    def flush_front_paragraph():
        nonlocal front_buf, front_count
        if not front_buf:
            return
        joined = collapse_ws(" ".join(front_buf))
        if joined:
            front_count += 1
            front_matter_paragraphs.append(
                Paragraph(
                    anchor=f"fa.{front_count}",
                    chapter=0,
                    page_start=0,
                    page_end=0,
                    text=joined,
                )
            )
        front_buf = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip running headers/footers.
        if is_running_line(line):
            i += 1
            continue

        # Skip form-feed page break markers (pdftotext emits \f between pages).
        if "\f" in line:
            i += 1
            continue

        # Skip Vellum scene-break ornaments. The typesetting places a small
        # decorative glyph between some paragraphs; pdftotext renders it as a
        # bare "∅" (U+2205) on its own centered line in the chapter body (and
        # as a bare "2" in the front matter, handled below). It carries no
        # text, and paragraphs in the body are already delimited by their
        # anchors, so we drop it exactly like a blank line -- otherwise it
        # surfaces as a spurious one-character "∅" paragraph in the output.
        if stripped == "∅":
            i += 1
            continue

        # Detect a chapter title page: centered number then (after blanks) an
        # all-caps title that may span 1-3 lines. Centered means indented at
        # least 4 spaces.
        m_chap = CHAPTER_HEADING_RE.match(line)
        if m_chap and not stripped.isdigit() is False:  # confirm it's just digits
            # Look ahead: must find an all-caps title within a few lines.
            chapter_num = int(stripped)
            # Only accept if monotonically increasing or first chapter.
            expected = (chapters[-1].number + 1) if chapters else 1
            if chapter_num == expected:
                title_lines: list[str] = []
                j = i + 1
                # Skip blank lines.
                while j < len(lines) and not lines[j].strip():
                    j += 1
                # Gather consecutive all-caps title lines (max 3).
                while (
                    j < len(lines)
                    and len(title_lines) < 3
                    and looks_like_all_caps_title(lines[j])
                ):
                    title_lines.append(lines[j].strip())
                    j += 1
                if title_lines:
                    # Flush any pending paragraph from previous chapter.
                    flush_paragraph()
                    if current is None:
                        flush_front_paragraph()
                    title = " ".join(title_lines)
                    # Normalize title case: ALL CAPS -> Title Case for display.
                    current = Chapter(number=chapter_num, title=title)
                    chapters.append(current)
                    i = j
                    continue

        # Paragraph anchor.
        anchor = parse_anchor(line)
        if anchor is not None:
            flush_paragraph()
            pending_anchor = anchor
            i += 1
            continue

        # Front-matter paragraph separator: bare "2" on its own line.
        # (Vellum ornament glyph that pdftotext mis-renders.)
        if current is None and stripped == "2":
            flush_front_paragraph()
            i += 1
            continue

        if stripped == "":
            # Blank line: paragraph-internal whitespace is preserved by
            # collapse_ws later, so we just move on.
            i += 1
            continue

        if current is None:
            front_buf.append(stripped)
        else:
            pending_text.append(stripped)
        i += 1

    flush_paragraph()
    if current is None:
        flush_front_paragraph()

    # Patch chapter openers' page range.
    # The print convention: each chapter's page numbering is cumulative across
    # the whole book (no per-chapter reset). The drop-cap opener has no anchor
    # in the print, so we infer: its start page = (previous chapter's last page
    # + 1), or 1 for chapter 1; its end page = (next explicit anchor's start
    # page - 1) if that's strictly later, otherwise the same page.
    prev_end = 0
    for ch in chapters:
        if not ch.paragraphs:
            continue
        opener = ch.paragraphs[0]
        is_placeholder = opener.anchor == f"{ch.number}.1" and opener.page_end == 1
        chapter_start = prev_end + 1 if prev_end > 0 else 1
        if is_placeholder:
            next_explicit = next(
                (p for p in ch.paragraphs[1:] if p.chapter == ch.number),
                None,
            )
            if next_explicit is None:
                opener.page_start = chapter_start
                opener.page_end = chapter_start
            else:
                opener.page_start = chapter_start
                opener.page_end = max(
                    chapter_start, next_explicit.page_start - 1
                )
            opener.anchor = _anchor_str(
                ch.number, opener.page_start, opener.page_end
            )
        prev_end = max(p.page_end for p in ch.paragraphs)

    return chapters, front_matter_paragraphs


def _anchor_str(ch: int, ps: int, pe: int) -> str:
    """Reconstruct the printed anchor string (e.g. '1.5-6', '48.1210-1')."""
    if pe == ps:
        return f"{ch}.{ps}"
    # Use the trailing-digit abbreviation the print uses, but only if
    # unambiguous; otherwise just write the full end page.
    pe_str = str(pe)
    ps_str = str(ps)
    # Match the printed convention: keep as many trailing digits as needed
    # to disambiguate. Find the longest common prefix of ps_str and pe_str
    # and keep just the differing tail of pe_str.
    common = 0
    for a, b in zip(ps_str, pe_str):
        if a == b:
            common += 1
        else:
            break
    abbrev = pe_str[common:] or pe_str
    return f"{ch}.{ps}-{abbrev}"


# ----- emit ------------------------------------------------------------------


def title_case(t: str) -> str:
    """Normalize an ALL CAPS chapter title to mixed case for display."""
    small = {"of", "the", "and", "in", "on", "to", "a", "an", "for", "or", "as", "by", "at", "from"}
    words = t.lower().split()
    out: list[str] = []
    for idx, w in enumerate(words):
        if idx != 0 and w in small and idx != len(words) - 1:
            out.append(w)
        else:
            # Preserve internal punctuation (e.g. "INTRODUCTION:" -> "Introduction:")
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def write_outputs(
    chapters: list[Chapter],
    front_matter: list[Paragraph],
    out_dir: Path,
    pdf_path: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    source = pdf_path.name
    digest = sha256_file(pdf_path)

    # Front matter.
    if front_matter:
        fm_path = out_dir / "front-matter.json"
        fm_path.write_text(
            json.dumps(
                {
                    "id": 0,
                    "canonical_id": "beelzebub/front-matter",
                    "urn": "urn:beelzebub:front-matter",
                    "title": "Friendly Advice",
                    "title_raw": "FRIENDLY ADVICE",
                    "title_slug": "friendly-advice",
                    "number": 0,
                    "page_start": 0,
                    "page_end": 0,
                    "kind": "front_matter",
                    "paragraphs": [p.__dict__ for p in front_matter],
                    "source": source,
                    "source_sha256": digest,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    for ch in chapters:
        if not ch.paragraphs:
            continue
        title_display = title_case(ch.title)
        page_start = min(p.page_start for p in ch.paragraphs)
        page_end = max(p.page_end for p in ch.paragraphs)
        data = {
            "id": ch.number,
            "canonical_id": f"beelzebub/ch{ch.number:02d}",
            "urn": f"urn:beelzebub:ch{ch.number:02d}",
            "title": title_display,
            "title_raw": ch.title,
            "title_slug": slugify(title_display),
            "number": ch.number,
            "page_start": page_start,
            "page_end": page_end,
            "paragraphs": [p.__dict__ for p in ch.paragraphs],
            "source": source,
            "source_sha256": digest,
        }
        out_path = out_dir / f"ch{ch.number:02d}.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pdf",
        type=Path,
        default=Path("Beelzebubs_Tales.pdf"),
        help="path to the source PDF",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("data"),
        help="output directory for per-chapter JSON",
    )
    args = ap.parse_args()

    if not args.pdf.exists():
        print(f"FATAL: PDF not found at {args.pdf}", file=sys.stderr)
        return 2

    print(f"Extracting text from {args.pdf}...", flush=True)
    text = run_pdftotext(args.pdf)
    print(f"  {len(text):,} characters, {text.count(chr(10)):,} lines", flush=True)

    print("Parsing...", flush=True)
    chapters, front_matter = parse(text)
    print(
        f"  {len(chapters)} chapters, "
        f"{sum(len(c.paragraphs) for c in chapters)} chapter paragraphs, "
        f"{len(front_matter)} front-matter paragraphs",
        flush=True,
    )

    write_outputs(chapters, front_matter, args.out, args.pdf)
    print(f"Wrote per-chapter JSON to {args.out}/", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
