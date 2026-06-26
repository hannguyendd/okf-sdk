# okf-core

Core library for **consuming** [Open Knowledge Format](SPEC.md) (OKF) bundles —
directories of markdown files with YAML frontmatter.

It can:

- parse and serialize individual OKF documents (`OKFDocument`),
- convert between concept ids and file paths,
- load a bundle directory into an in-memory concept graph with cross-links and
  reverse backlinks (`Bundle`),
- regenerate the bundle's `index.md` progressive-disclosure listings
  (`regenerate_indexes`).

It does **not** produce bundles (no data-source ingestion, web crawling, agent,
or LLM calls) and ships no UI. Its only runtime dependency is PyYAML.

## Usage

```python
from okf_core import Bundle, OKFDocument, regenerate_indexes

bundle = Bundle.load("path/to/bundle")
for concept in bundle:
    print(concept.id, concept.type, concept.title)

print(bundle.edges())               # [(source_id, target_id), ...]
print(bundle.backlinks("tables/users"))

regenerate_indexes("path/to/bundle")  # writes index.md files
```

See [SPEC.md](SPEC.md) for the format this library implements, and
[CONFORMANCE.md](CONFORMANCE.md) for the numbered, checkable rules a bundle must
satisfy to be conformant.
