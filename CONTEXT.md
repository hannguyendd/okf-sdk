# Open Knowledge Format (OKF)

The domain of this repository: an open, human- and agent-friendly format for
representing knowledge as a directory of markdown files with YAML frontmatter.
Tooling in this repository reads (`okf-core`) and authors (`okf-backend`, `okf-mcp`)
this format.

## Language

**Bundle**:
A self-contained, hierarchical collection of knowledge documents. The unit of
distribution. The OKF spec's term for the on-disk unit; in this repository a
workspace is exactly one bundle. Not a name for a top-level directory.
_Avoid_: Repo, package, corpus

**Storage**:
The interface through which a bundle's files are read and written, so a bundle
can live on a local disk or another backend (object store, remote git,
database). Addressed by bundle-relative keys; the local filesystem is the
default backend.
_Avoid_: Filesystem, disk, backend (as the name of the interface)

**Workspace**:
A named, git-repo-shaped directory at `~/.okf/workspaces/<name>` (the `.okf`
home is overridable via `OKF_HOME`) that is exactly one bundle, plus hidden
`.okf/` metadata. The unit git will manage, and what one MCP server serves.
_Avoid_: Project, vault, store, index, bundle (as a name for a top-level directory)

**Node**:
A directory or a concept, addressed by a path relative to the workspace root.
_Avoid_: Entry, item

**Concept**:
A single unit of knowledge, represented as exactly one markdown document.
_Avoid_: Document, entry

**Directory**:
A folder within a bundle that groups related concepts. Its layout is
domain-independent — chosen by the producer to suit the knowledge, not dictated
by OKF.
_Avoid_: Folder, subfolder, group

**Directory description**:
A one-line statement of a directory's purpose — what knowledge it holds and why
it exists. Authored when present; otherwise synthesized from the directory's
contents as a fallback.
_Avoid_: Role, domain, responsibility, charter, summary

**Directory listing** (`_index.md`):
A per-directory listing that enumerates the directory's contents for progressive
disclosure. Machine-generated in full, except for an optional authored
`description` in its frontmatter. Not a concept.
_Avoid_: Index, TOC, manifest, catalog

**Synthesized description**:
The fallback directory description auto-derived from a directory's contents when
no description has been authored. A contents summary, not a statement of purpose.
_Avoid_: Generated description, auto-summary
