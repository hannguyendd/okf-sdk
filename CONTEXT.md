# Open Knowledge Format (OKF)

The domain of this repository: an open, human- and agent-friendly format for
representing knowledge as a directory of markdown files with YAML frontmatter.
Tooling in this workspace reads (`okf-core`) and authors (`okf-mcp`) bundles in
this format.

## Language

**Bundle**:
A self-contained, hierarchical collection of knowledge documents. The unit of
distribution. The on-disk form of an index.
_Avoid_: Repo, package, corpus

**Storage**:
The interface through which a bundle's files are read and written, so a bundle
can live on a local disk or another backend (object store, remote git,
database). Addressed by bundle-relative keys; the local filesystem is the
default backend.
_Avoid_: Filesystem, disk, backend (as the name of the interface)

**Workspace**:
A named, git-repo-shaped directory at `~/.okf/workspaces/<name>` (the `.okf`
home is overridable via `OKF_HOME`) that holds one or more indexes. The unit git
will manage.
_Avoid_: Project, vault, store (store = `OKF_STORE_ROOT` per-project mode)

**Index**:
A collection of concepts inside a workspace; exactly one bundle. Each visible
top-level directory of a workspace is an index, named by its directory.
_Avoid_: Collection, `_index.md` (that is a directory listing)

**Concept**:
A single unit of knowledge, represented as exactly one markdown document.
_Avoid_: Document, entry, node

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
_Avoid_: Index (now means a workspace's collection of concepts), TOC, manifest, catalog

**Synthesized description**:
The fallback directory description auto-derived from a directory's contents when
no description has been authored. A contents summary, not a statement of purpose.
_Avoid_: Generated description, auto-summary
