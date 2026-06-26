# OKF Bundle Conformance Rules — design

**Date:** 2026-06-26
**Status:** Design (awaiting review)
**Deliverable:** `packages/okf-core/CONFORMANCE.md`
**Derived solely from:** `packages/okf-core/SPEC.md` (Open Knowledge Format v0.1)

## Purpose & scope

Produce a **normative, format-agnostic** companion to `SPEC.md`: a single
document that turns the spec's prose into individually numbered, checkable
**bundle conformance rules**. The deliverable answers one question — *"is this
directory a conformant OKF v0.1 bundle?"* — with rules a human or an agent can
apply mechanically.

### In scope

- **Bundle conformance only.** Rules constrain the *bundle artifact* (its files,
  frontmatter, reserved-file structure). The bundle is the subject of every rule.
- Each rule carries a **stable ID**, an **RFC-2119 keyword**, a one-line **"how
  to verify"**, and a **SPEC reference**.
- An explicit **"Explicitly permitted — not violations"** section that fences in
  the hard rules using SPEC §9's permissive consumption model.

### Out of scope

- **Reader/consumer behavior rules.** What a consumer MUST tolerate is captured
  only indirectly, as the "not a violation" boundary on bundle rules — not as a
  separate obligation set.
- **Producer/agent workflow rules.** No "how to author" guidance beyond what the
  bundle artifact must end up looking like.
- **Library specifics.** No okf-core implementation details. Verification hints
  describe *what* to check, not okf-core internals (the doc stays usable by any
  implementation).

### Non-negotiable, defined precisely

The user's requirement that "rules must conform and NOT negotiate" is encoded as
the **conformance-level** semantics:

- **MUST / MUST NOT** — *conformance-blocking*. A bundle that violates **any one**
  is **non-conformant**. These are the non-negotiable rules.
- **SHOULD** — recommended. Violation degrades quality/interop but does **not**
  break conformance.
- **MAY / Permitted** — explicit latitude; never a violation.

## Grounding principle

Every rule is derived **solely** from `SPEC.md` (OKF v0.1). This document adds no
new constraints — it only sharpens existing spec prose into individually
checkable rules. Where the spec is loose (e.g. §6 index structure), only the
concretely checkable parts become MUST; the soft parts become SHOULD.

## Format decisions

- **Approach:** category-grouped rule tables (one table per SPEC area), each rule
  on its own row. Chosen over a single flat table (loses traceability) and a
  two-tier "core + extended" split (blurs completeness).
- **ID scheme:** `CATEGORY-NN`, stable and citable (e.g. "fails `FM-01`").
  Categories: `DOC` (document structure), `FM` (frontmatter), `RSV` (reserved
  files), `LNK` (cross-links), `IDX` (index files), `LOG` (log files), `CIT`
  (citations), `VER` (versioning).
- **Row columns:** `ID | Level | Rule | How to verify | SPEC`.

## Document layout (CONFORMANCE.md)

1. Title + one-paragraph purpose + grounding principle.
2. **Conformance levels** (the MUST/SHOULD/MAY semantics above).
3. **Conformant bundle — summary**: a bundle is conformant iff it violates no
   MUST/MUST NOT rule (i.e. `DOC-01..03`, `FM-01`, `RSV-01/02`, `IDX-01/02`,
   `LOG-01`).
4. Rule tables by category (see inventory below).
5. **Explicitly permitted — NOT violations** (from §9).
6. Short appendix: rule-ID index / changelog stub for future OKF versions.

## Complete rule inventory

Conformance-blocking rules are **MUST / MUST NOT**. Everything else is guidance.

### DOC — concept document structure

| ID | Level | Rule | SPEC |
|----|-------|------|------|
| DOC-01 | MUST | Every concept document is valid UTF-8. | §4 |
| DOC-02 | MUST | A concept doc begins with a frontmatter block: a line that is exactly `---`, a YAML body, then a closing line exactly `---`. | §4, §9.1 |
| DOC-03 | MUST | The frontmatter parses as YAML **and is a mapping** (not a scalar or sequence). | §4.1, §9.1 |
| DOC-04 | SHOULD | Bodies favor structural markdown (headings, lists, tables, code fences) over freeform prose. | §4.2 |

### FM — frontmatter fields

| ID | Level | Rule | SPEC |
|----|-------|------|------|
| FM-01 | MUST | Frontmatter contains a `type` key whose value is a non-empty string. | §4.1, §9.2 |
| FM-02 | SHOULD | Include `title`, `description`, `resource` (when bound to a resource), `tags`, and `timestamp`. | §4.1 |
| FM-03 | SHOULD | `timestamp`, when present, is an ISO 8601 datetime. | §4.1 |
| FM-04 | SHOULD | `tags`, when present, is a YAML list of short strings. | §4.1 |
| FM-05 | MAY | Frontmatter may carry any additional producer-defined keys. | §4.1 |

### RSV — reserved files

| ID | Level | Rule | SPEC |
|----|-------|------|------|
| RSV-01 | MUST NOT | `index.md` and `log.md` are not used as concept documents. | §3.1 |
| RSV-02 | MUST | Every `.md` file is either a reserved file (`index.md`/`log.md`) or a concept document; there is no third role. | §3, §3.1 |

### LNK — cross-links

| ID | Level | Rule | SPEC |
|----|-------|------|------|
| LNK-01 | SHOULD | Cross-links use standard markdown link syntax; bundle-relative absolute links (`/path.md`) are the recommended form. | §5.1, §5.2 |
| LNK-02 | MAY | A link whose target does not exist in the bundle is permitted (broken links are **not** malformed). | §5.3 |

### IDX — index files

| ID | Level | Rule | SPEC |
|----|-------|------|------|
| IDX-01 | MUST NOT | An `index.md` carries no frontmatter — **except** the bundle-root `index.md`, which may carry frontmatter solely to declare `okf_version`. | §6, §11 |
| IDX-02 | MUST | When present, an `index.md` body consists of one or more `#` section headings whose entries are markdown-link list items pointing at concepts/subdirectories. | §6, §9.3 |
| IDX-03 | SHOULD | Index entries include the linked concept's `description`. | §6 |

### LOG — log files

| ID | Level | Rule | SPEC |
|----|-------|------|------|
| LOG-01 | MUST | When present, a `log.md` groups entries under date headings, and every date heading uses ISO 8601 `YYYY-MM-DD` form. | §7, §9.3 |
| LOG-02 | SHOULD | Entries are ordered newest-first. | §7 |
| LOG-03 | MAY | A leading bold keyword (`**Update**`, `**Creation**`, …) on each entry is convention, not required. | §7 |

### CIT — citations

| ID | Level | Rule | SPEC |
|----|-------|------|------|
| CIT-01 | SHOULD | External sources backing body claims are listed under a `# Citations` heading at the bottom, numbered. | §8 |
| CIT-02 | MAY | Citation links may be absolute URLs, bundle-relative paths, or paths into a `references/` subdirectory. | §8 |

### VER — versioning

| ID | Level | Rule | SPEC |
|----|-------|------|------|
| VER-01 | MAY | A bundle may declare its OKF version via `okf_version` in the bundle-root `index.md` frontmatter — the only place frontmatter is permitted in any `index.md`. | §11 |

## Explicitly permitted — NOT conformance violations (§9)

The published doc lists these prominently so the MUST rules are not over-read.
None of the following make a bundle non-conformant:

- Missing optional frontmatter fields (`title`, `description`, `resource`,
  `tags`, `timestamp`).
- Unknown / non-registered `type` values.
- Unknown additional frontmatter keys.
- Broken cross-links (dangling link targets).
- Missing `index.md` files at any level (including the root).

## Conformance-blocking spine (summary)

A bundle is **conformant with OKF v0.1** iff it violates none of:
`DOC-01`, `DOC-02`, `DOC-03`, `FM-01`, `RSV-01`, `RSV-02`, `IDX-01`, `IDX-02`,
`LOG-01`.

In published `CONFORMANCE.md` each MUST/MUST NOT rule also carries a one-line
**"How to verify"** column (omitted here for brevity; see the sample in the
design discussion). SHOULD/MAY rows carry no verification (nothing to fail).
