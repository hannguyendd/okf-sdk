# Directory descriptions live in `_index.md` frontmatter

A directory's authored description (a one-line statement of its purpose) is stored
as a `description` key in that directory's own `_index.md` frontmatter. The index
regenerator reads and preserves this key, lifts it into the parent index's caption
for the subdirectory, and falls back to a synthesized contents summary when the key
is absent. We chose this because `_index.md` is the file consumers already fetch for
progressive disclosure, so the description reaches them with no extra reads.

## Considered options

- **Frontmatter in `_index.md` (chosen).** Smallest structural change; reuses the
  one existing exception for `_index.md` frontmatter (root `okf_version`). Costs the
  clean "`_index.md` is 100% generated" invariant — the regenerator becomes
  read-preserve-rewrite rather than pure-rewrite.
- **A new reserved file (`_dir.md`).** Keeps `_index.md` fully generated, but adds a
  third reserved filename (rippling through `RSV-*`, `constants.py`, and the spec)
  and — decisively — the description would never reach consumers, since `read_index`
  reads only `_index.md`. Delivering it would require a second file read per
  directory: more context and more round-trips, not less.
- **A prose preamble in the `_index.md` body.** No frontmatter, but the regenerator
  rewrites the body wholesale, so an authored preamble would need a fragile
  preserved region, and "the first paragraph" is a loose contract to parse.

## Consequences

- Relaxes conformance rule `IDX-01` (and generalizes `VER-01`): `_index.md`
  frontmatter is now permitted at any level, restricted to a **tight allowlist** —
  `description` (any level) and `okf_version` (bundle root only). Any other key is
  non-conformant. `description` is `SHOULD`, not `MUST`: bundles without it stay
  conformant and get the synthesized fallback.
- OKF 0.1 is still an unreleased draft, so this is folded into the 0.1 draft in
  place rather than cut as a new version — there are no shipped 0.1 consumers to
  gate behind an `okf_version` bump.
