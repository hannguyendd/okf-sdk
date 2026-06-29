# okf-core

Core library for **consuming** [Open Knowledge Format](SPEC.md) (OKF) bundles —
directories of markdown files with YAML frontmatter.

It can:

- parse and serialize individual OKF documents (`OKFDocument`),
- convert between concept ids and file paths,
- load a bundle directory into an in-memory concept graph with cross-links and
  reverse backlinks (`Bundle`),
- regenerate the bundle's `_index.md` progressive-disclosure listings
  (`regenerate_indexes`),
- validate a bundle against the conformance-blocking MUST rules
  (`validate_bundle`, or `python -m okf_core.validate <bundle>`); see
  [CONFORMANCE.md](CONFORMANCE.md).

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

regenerate_indexes("path/to/bundle")  # writes _index.md files

from okf_core import validate_bundle
for v in validate_bundle("path/to/bundle"):
    print(v.path, v.rule, v.message)  # empty list ⇒ conformant
```

Or from the command line (exit `0` = conformant, `1` = violations, `2` = bad
usage):

```bash
python -m okf_core.validate path/to/bundle
```

See [SPEC.md](SPEC.md) for the format this library implements, and
[CONFORMANCE.md](CONFORMANCE.md) for the numbered, checkable rules a bundle must
satisfy to be conformant.
