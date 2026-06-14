<div align="center">

# Beelzebub's Tales

**A clean, citable edition of G. I. Gurdjieff's *Beelzebub's Tales to His Grandson***

[![License: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![Data: public domain](https://img.shields.io/badge/Data-public%20domain-lightgrey.svg)](LICENSE-DATA)
[![Live PWA](https://img.shields.io/badge/Live-PWA-orange.svg)](https://sajad2025.github.io/beelzebub/)

[**Open the app →**](https://sajad2025.github.io/beelzebub/)

</div>

---

## What this is

*Beelzebub's Tales to His Grandson* (1950, All and Everything First Series) is
G. I. Gurdjieff's principal published work — a deliberately strange, 1,238-page
allegorical novel that he intended to be read three times: once mechanically,
once aloud, and once to "fathom the gist."

This project mirrors the full English text into a schema-documented, citable
JSON form, and ships a small reference reader (Progressive Web App) on top.

**The reader is the demo. The data is the product.** The goal is a small,
durable piece of infrastructure for anyone — readers, app developers,
scholars — who wants to work with *Beelzebub's Tales* in a programmable form.

---

## Who is this for?

| You are a… | Start here |
|---|---|
| 📖 **Reader** | [Open the app](https://sajad2025.github.io/beelzebub/) — install via Chrome (Android/desktop: three-dot menu → *Install app*) or Safari (iOS: Share → *Add to Home Screen*) |
| 💻 **Developer** | [`/data`](./data) — per-chapter JSON; [`schema/`](./schema) — JSON Schema |
| 🎓 **Researcher** | Anchored paragraphs cross-reference the printed page; [`MANIFEST.json`](./MANIFEST.json) ships counts + provenance |
| ✍️ **Contributor** | Open an issue or PR — anything from data corrections to reader polish |

---

## What's in v0.2

- **All 48 chapters**, fully extracted, ~6,577 paragraphs, 1,238 pages
- **Per-paragraph anchors** in the form `1.4`, `1.5-6`, `48.1210-1`, preserved
  verbatim from the print and cross-stored as structured `page_start` /
  `page_end`
- **Front matter** (the *Friendly Advice* preface) extracted to
  `front-matter.json`
- **Reader PWA** — single-file React app: sepia / light / dark themes,
  Crimson Pro & Lora serifs, four text sizes, persistent settings, deep-linkable
  anchor URLs (`#/ch/1/1.5`)
- **Anchor search** — type `1.5`, `10.2`, `48.1210-1` to jump directly to
  the printed page from anywhere in the app
- **Full-text search** — chapters load lazily into an in-memory index on first
  text query
- **Frozen schema v1** with JSON Schema validation built into the manifest step

- **Installable PWA** — manifest with maskable icons, service worker that
  precaches the shell and lazy-caches chapter JSON, so the app loads instantly
  and works fully offline after first visit

Out of v0.2 (planned for v0.3): SQLite + Parquet dumps with DOI,
audio recitations.

---

## The anchor convention — the long-term contract

Every paragraph in *Beelzebub's Tales* carries a small anchor in the print,
which we preserve as a citation system:

```
1.4         — chapter 1, page 4 of the printed book
1.5-6       — chapter 1, paragraph spans pages 5 and 6
48.1210-1   — chapter 48, pages 1210 and 1211 (trailing-digit abbreviation)
```

These anchors are **never reused or repointed** — they refer back to a
specific 2019 typesetting of the public-domain text. The reader's URLs encode
them directly:

```
https://sajad2025.github.io/beelzebub/#/ch/1/1.5
https://sajad2025.github.io/beelzebub/#/ch/48/48.1210-1
```

Use these in citations, course materials, study notes — they will resolve in
2040.

---

## Data shape

```json
{
  "id": 1,
  "canonical_id": "beelzebub/ch01",
  "urn": "urn:beelzebub:ch01",
  "title": "The Arousing of Thought",
  "title_raw": "THE AROUSING OF THOUGHT",
  "title_slug": "the-arousing-of-thought",
  "number": 1,
  "page_start": 1,
  "page_end":  50,
  "paragraphs": [
    {
      "anchor": "1.1-2",
      "chapter": 1,
      "page_start": 1,
      "page_end": 2,
      "text": "Among other convictions formed in my common presence…"
    },
    {
      "anchor": "1.3",
      "chapter": 1,
      "page_start": 3,
      "page_end": 3,
      "text": "That is why I now, also, setting forth on this venture…"
    }
  ],
  "source": "Beelzebubs_Tales.pdf",
  "source_sha256": "07a485ba…"
}
```

Full schema: [`schema/v1.json`](./schema/v1.json). Frozen — breaking changes
require schema v2.

---

## Reproducing the data

The data layer is fully reproducible from the source PDF that lives in the
repo. One system dependency:

```bash
brew install poppler           # gives pdftotext

# Reproduce data/ + MANIFEST.json + CHECKSUMS.sha256
python3 scripts/extract_pdf.py
python3 scripts/build_manifest.py
```

Optional `pip install -r scripts/requirements.txt` enables JSON-Schema
validation during the manifest step.

## Running the reader locally

```bash
python3 -m http.server 8765    # any static file server works
open http://localhost:8765/
```

The reader is a single-file React app (Tailwind + Babel-standalone) served as
plain static files. No build step.

---

## Versioning

- **Code** — [SemVer](https://semver.org) (`0.2.0`)
- **Schema** — SemVer (`v1`, `v2`) — frozen between majors
- **Corpus** — pinned to the SHA-256 of `Beelzebubs_Tales.pdf` in
  `MANIFEST.json`

---

## Licensing

| Layer | License |
|---|---|
| Reader app, scripts, schema | [MIT](./LICENSE) |
| Extracted text | Public domain (life+70; PD since 2020) — see [LICENSE-DATA](./LICENSE-DATA) |
| Source PDF (typesetting) | Re-typeset by *joshuatilton* via Vellum (2019) of the underlying public-domain text |

**Suggested attribution for downstream reuse:**

> *Beelzebub's Tales to His Grandson*, by G. I. Gurdjieff (1950). Text in the
> public domain. Machine-readable JSON edition via
> [sajad2025/beelzebub](https://github.com/sajad2025/beelzebub), anchored to
> the joshuatilton/Vellum 2019 typesetting.

---

## How to cite

See [`CITATION.cff`](./CITATION.cff) — GitHub renders a "Cite this repository"
button at the top of this page with BibTeX export.

---

## Acknowledgements

- **G. I. Gurdjieff** (1866–1949) — author of the text.
- **joshuatilton** — for the careful 2019 typesetting whose page anchors this
  project preserves as a citation system.
- **Vellum** — the publishing tool used to produce the source PDF.
- **Crimson Pro** (Sebastian Kosch / Jacques Le Bailly, OFL) and **Lora**
  (Cyreal, OFL) — the reading fonts.
- **[sajad2025/ganjoor](https://github.com/sajad2025/ganjoor)** — the sibling
  project (classical Persian poetry) whose visual design language this reader
  shares.

---

## Status

🌱 **Pre-alpha (v0.2).** Data layer and reader both shipped. Schema frozen.
APIs may change. PRs and issues welcome.

— Started May 2026 from a phone, no laptop, no PC.
