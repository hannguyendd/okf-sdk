# OKF Bundle Conformance Rules

**Version 0.1 — normative companion to [`SPEC.md`](SPEC.md)**

This document turns the prose of the Open Knowledge Format specification
(OKF v0.1) into a set of individually numbered, mechanically checkable rules. It
answers exactly one question:

> **Is this directory a conformant OKF v0.1 bundle?**

Every rule is derived **solely** from `SPEC.md`. This document introduces **no
new constraints** — it only sharpens the spec's existing language into rules that
can be cited (e.g. "fails `FM-01`") and verified one at a time. Where the spec is
deliberately loose, only the concretely checkable parts are conformance-blocking;
the rest is recorded as guidance.

The subject of every rule is the **bundle artifact** — its files, their
frontmatter, and the structure of reserved files. Reader/consumer behavior is out
of scope and appears here only as the boundary of what is *not* a violation.

---

## 1. Bundle structure, files, and fields

This section orients you before the rules. It is a summary of `SPEC.md` §2–§4;
the rule tables in §4 are what actually decide conformance.

### 1.1 Structure

A **bundle** is a directory tree of markdown files — the unit of distribution. Its
directory layout is **domain-independent**: producers organize concepts however
makes sense for the knowledge being captured. A bundle may be shipped as a git
repository (recommended), an archive, or a subdirectory of a larger repo.

```
path/to/bundle/
├── index.md              # optional — directory listing (progressive disclosure)
├── log.md                # optional — chronological update history
├── <concept>.md          # a concept at the bundle root
└── <subdirectory>/       # subdirectories group concepts
    ├── index.md
    ├── <concept>.md
    └── <subdirectory>/
        └── …
```

A **concept** is one unit of knowledge — exactly one markdown document. Its
**concept ID** is the file's bundle-relative path with the `.md` suffix removed
(e.g. `tables/users.md` → `tables/users`). The implicit parent/child hierarchy
comes from the directory tree; any other relationship is expressed with a
**cross-link** (a markdown link to another concept).

### 1.2 File roles

Every `.md` file plays exactly one of three roles (`RSV-02`). The two reserved
filenames are special at **any** level of the tree and must never be a concept
(`RSV-01`).

| File | Role | Frontmatter? | Governing rules |
|------|------|--------------|-----------------|
| `<name>.md` (concept) | A single unit of knowledge — a tangible asset (table, API), an abstract idea (metric, process), or anything between. | **Required** — a YAML mapping with a `type` (§1.3). | `DOC-*`, `FM-*` |
| `index.md` | Directory listing enabling **progressive disclosure** — lets a reader see what is available before opening documents. | **None** — except the bundle-root `index.md`, which may declare `okf_version`. | `IDX-*`, `VER-01` |
| `log.md` | Chronological history of changes to the scope (level) it sits in. | **None.** | `LOG-*` |

### 1.3 Frontmatter fields

Frontmatter is the YAML mapping at the top of every concept document. Only `type`
is required; the rest are recommended or free. Consumers preserve unknown keys and
never reject a document for an unrecognized field.

| Field | Status | Purpose | Rule |
|-------|--------|---------|------|
| `type` | **Required** | Short string naming the kind of concept (e.g. `BigQuery Table`, `Metric`, `Playbook`). Drives routing, filtering, presentation. Not registered centrally — any non-empty string is valid. | `FM-01` |
| `title` | Recommended | Human-readable display name. If absent, a title may be derived from the filename. | `FM-02` |
| `description` | Recommended | One-sentence summary. Used in `index.md` entries, search snippets, previews. | `FM-02` |
| `resource` | Recommended (when the concept is bound to a resource) | Canonical URI of the underlying asset. Absent for purely abstract concepts. | `FM-02` |
| `tags` | Recommended | YAML list of short strings for cross-cutting categorization. | `FM-02`, `FM-04` |
| `timestamp` | Recommended | ISO 8601 datetime of the last meaningful change. | `FM-02`, `FM-03` |
| *(any other key)* | Optional | Producer-defined extension. Preserved on round-trip; never a rejection cause. | `FM-05` |
| `okf_version` | Optional — **bundle-root `index.md` only** | Declares the OKF version the bundle targets. The only frontmatter permitted in any `index.md`. | `VER-01` |

The body (everything after the closing `---`) is free-form markdown. These
heading names carry **conventional** meaning and should be used when applicable:
`# Schema` (an asset's columns/fields), `# Examples` (usage), `# Citations`
(external sources — see `CIT-01`).

---

## 2. Conformance levels

The keywords below are non-negotiable in meaning. They follow RFC 2119.

| Level | Meaning | Effect on conformance |
|-------|---------|-----------------------|
| **MUST** / **MUST NOT** | A hard requirement. | **Conformance-blocking.** A bundle that violates *any one* MUST or MUST NOT rule is **non-conformant**. These are the non-negotiable rules. |
| **SHOULD** | A strong recommendation. | **Not** conformance-blocking. Violation degrades quality and interoperability but does not make a bundle non-conformant. |
| **MAY** / **Permitted** | Explicit latitude. | Never a violation. Listed so the hard rules are not over-read. |

A bundle is **conformant with OKF v0.1** if and only if it violates none of the
MUST / MUST NOT rules in §4:

> `DOC-01`, `DOC-02`, `DOC-03`, `FM-01`, `RSV-01`, `RSV-02`, `IDX-01`,
> `IDX-02`, `LOG-01`.

Everything else in this document is guidance (`SHOULD`) or explicit permission
(`MAY`).

---

## 3. How to read the rule tables

Each rule has a stable **ID** (`CATEGORY-NN`), a **Level**, the **Rule**, a
one-line **How to verify**, and the originating **SPEC** section. MUST / MUST NOT
rows always carry a verification check. `SHOULD` / `MAY` rows have nothing that
can *fail*, so their verification cell is `—`.

Categories: `DOC` document structure · `FM` frontmatter · `RSV` reserved files ·
`LNK` cross-links · `IDX` index files · `LOG` log files · `CIT` citations ·
`VER` versioning.

---

## 4. Rules

### 4.1 DOC — concept document structure

| ID | Level | Rule | How to verify | SPEC |
|----|-------|------|---------------|------|
| **DOC-01** | MUST | Every concept document is valid UTF-8. | File decodes as UTF-8 with no error. | §4 |
| **DOC-02** | MUST | A concept document begins with a frontmatter block: a first line that is exactly `---`, a YAML body, and a closing line that is exactly `---`. | First line equals `---`; a later line on its own equals `---`, closing the block. | §4, §9.1 |
| **DOC-03** | MUST | The frontmatter block parses as YAML **and is a mapping** — not a scalar or a sequence. | YAML parse of the block succeeds and yields key/value pairs (a mapping). | §4.1, §9.1 |
| **DOC-04** | SHOULD | Bodies favor structural markdown (headings, lists, tables, fenced code) over freeform prose. | — | §4.2 |

### 4.2 FM — frontmatter fields

| ID | Level | Rule | How to verify | SPEC |
|----|-------|------|---------------|------|
| **FM-01** | MUST | Frontmatter contains a `type` key whose value is a non-empty string. | `type` key present; value is a string; non-empty after trimming whitespace. | §4.1, §9.2 |
| **FM-02** | SHOULD | Include `title`, `description`, `resource` (when the concept is bound to a resource), `tags`, and `timestamp`. | — | §4.1 |
| **FM-03** | SHOULD | `timestamp`, when present, is an ISO 8601 datetime. | — | §4.1 |
| **FM-04** | SHOULD | `tags`, when present, is a YAML list of short strings. | — | §4.1 |
| **FM-05** | MAY | Frontmatter may carry any additional producer-defined keys. | — | §4.1 |

### 4.3 RSV — reserved files

| ID | Level | Rule | How to verify | SPEC |
|----|-------|------|---------------|------|
| **RSV-01** | MUST NOT | `index.md` and `log.md` are not used as concept documents. | No file named `index.md` or `log.md` is treated or validated as a concept. | §3.1 |
| **RSV-02** | MUST | Every `.md` file in the tree is either a reserved file (`index.md` / `log.md`) or a concept document — there is no third role. | Each `.md` file classifies as `index.md`, `log.md`, or a concept document. | §3, §3.1 |

### 4.4 LNK — cross-links

| ID | Level | Rule | How to verify | SPEC |
|----|-------|------|---------------|------|
| **LNK-01** | SHOULD | Cross-links use standard markdown link syntax; bundle-relative absolute links (`/path/to/x.md`) are the recommended form. | — | §5.1, §5.2 |
| **LNK-02** | MAY | A link whose target does not exist in the bundle is permitted — broken links are **not** malformed. | — | §5.3 |

### 4.5 IDX — index files

| ID | Level | Rule | How to verify | SPEC |
|----|-------|------|---------------|------|
| **IDX-01** | MUST NOT | An `index.md` carries no frontmatter — **except** the bundle-root `index.md`, which may carry frontmatter solely to declare `okf_version`. | A non-root `index.md` has no leading `---` block. A root `index.md` with frontmatter declares only `okf_version`. | §6, §11 |
| **IDX-02** | MUST | When present, an `index.md` body consists of one or more `#` section headings whose entries are markdown-link list items pointing at concepts or subdirectories. | File contains ≥1 heading; list entries are markdown links. | §6, §9.3 |
| **IDX-03** | SHOULD | Each entry includes the linked concept's `description`. | — | §6 |

### 4.6 LOG — log files

| ID | Level | Rule | How to verify | SPEC |
|----|-------|------|---------------|------|
| **LOG-01** | MUST | When present, a `log.md` groups entries under date headings, and every date-group heading uses ISO 8601 `YYYY-MM-DD` form. | Every date-group heading matches `YYYY-MM-DD`. | §7, §9.3 |
| **LOG-02** | SHOULD | Entries are ordered newest-first. | — | §7 |
| **LOG-03** | MAY | A leading bold keyword on each entry (`**Update**`, `**Creation**`, `**Deprecation**`, …) is convention, not required. | — | §7 |

### 4.7 CIT — citations

| ID | Level | Rule | How to verify | SPEC |
|----|-------|------|---------------|------|
| **CIT-01** | SHOULD | External sources backing body claims are listed under a `# Citations` heading at the bottom of the document, numbered. | — | §8 |
| **CIT-02** | MAY | Citation links may be absolute URLs, bundle-relative paths, or paths into a `references/` subdirectory. | — | §8 |

### 4.8 VER — versioning

| ID | Level | Rule | How to verify | SPEC |
|----|-------|------|---------------|------|
| **VER-01** | MAY | A bundle may declare its OKF version via `okf_version` in the bundle-root `index.md` frontmatter — the only place frontmatter is permitted in any `index.md`. | — | §11 |

---

## 5. Explicitly permitted — NOT conformance violations

The permissive consumption model of SPEC §9 is part of the format. The following
do **not** make a bundle non-conformant, and an implementation **must not** reject
a bundle for any of them:

- Missing optional frontmatter fields (`title`, `description`, `resource`,
  `tags`, `timestamp`).
- Unknown or non-registered `type` values — `type` is never validated against a
  registry (see `FM-01`: any non-empty string passes).
- Unknown additional frontmatter keys.
- Broken cross-links (dangling link targets) — see `LNK-02`.
- Missing `index.md` files at any level, including the bundle root.

This latitude is intentional: it keeps a bundle usable as it grows, is
refactored, and is partially generated by agents.

---

## Appendix A — Rule index

**Conformance-blocking (MUST / MUST NOT):**
`DOC-01`, `DOC-02`, `DOC-03`, `FM-01`, `RSV-01`, `RSV-02`, `IDX-01`, `IDX-02`,
`LOG-01`.

**Guidance (SHOULD):**
`DOC-04`, `FM-02`, `FM-03`, `FM-04`, `LNK-01`, `IDX-03`, `LOG-02`, `CIT-01`.

**Permitted (MAY):**
`FM-05`, `LNK-02`, `LOG-03`, `CIT-02`, `VER-01`.

## Appendix B — Versioning of these rules

These rules track OKF v0.1. Rule IDs are stable: a rule is never renumbered.
Future OKF versions add, deprecate, or re-level rules by appending to the tables
and noting the change here. A minor OKF bump may add `SHOULD` / `MAY` rules or
relax a `MUST`; a major bump may add or tighten `MUST` / `MUST NOT` rules.
