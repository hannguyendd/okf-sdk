/** Typed client for the okf-backend HTTP API (`packages/okf-backend/src/okf_backend/api.py`). */

export interface Info { mode: "workspace"; location: string; read_only: boolean; search_enabled: boolean }
/** Crayon colours a workspace can be tagged with (okf_core.WORKSPACE_COLORS). */
export type WorkspaceColor = "yellow" | "pink" | "green" | "blue" | "red" | "orange" | "purple";
export interface WorkspaceInfo { name: string; color: WorkspaceColor | null }
export interface DirEntry { name: string; dir: string; description: string | null }
export interface ConceptMeta { id: string; type: string | null; title: string | null; description: string | null; tags: string[] }
export interface Tree { dir: string; description: string | null; directories: DirEntry[]; concepts: ConceptMeta[] }
export interface Concept { id: string; frontmatter: Record<string, unknown>; body: string; links_to: string[]; linked_from?: string[] }
/** A search hit: one directory listing (`_index.md`) that matched. */
export interface Hit { kind: "index"; dir: string; path: string; score: number; excerpt: string }
export interface DeleteResult { action: string; referenced_by?: string[] }
export interface Overview {
  concepts: number;
  directories: number;
  types: Record<string, number>;
  recent: { id: string; title: string | null; type: string | null; timestamp: string | null }[];
}

/** The workspace a request targets. */
export interface Scope { ws: string }

export class ApiError extends Error {}

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.error ?? `HTTP ${res.status}`);
  return data as T;
}

const seg = encodeURIComponent;
const path = (id: string) => id.split("/").map(seg).join("/");
const base = (s: Scope) => `/api/workspaces/${seg(s.ws)}`;

export const api = {
  info: () => call<Info>("GET", "/api/info"),
  workspaces: () => call<WorkspaceInfo[]>("GET", "/api/workspaces"),
  createWorkspace: (name: string) => call<WorkspaceInfo>("POST", "/api/workspaces", { name }),
  setWorkspaceColor: (ws: string, color: WorkspaceColor | null) =>
    call<{ name: string; color: WorkspaceColor | null }>("POST", `/api/workspaces/${seg(ws)}/color`, { color }),

  tree: (s: Scope, dir: string) => call<Tree>("GET", `${base(s)}/tree?dir=${seg(dir)}`),
  concept: (s: Scope, id: string) => call<Concept>("GET", `${base(s)}/concepts/${path(id)}`),
  add: (s: Scope, concept_id: string, frontmatter: Record<string, unknown>, body: string) =>
    call("POST", `${base(s)}/concepts`, { concept_id, frontmatter, body }),
  patch: (s: Scope, id: string, frontmatter: Record<string, unknown>, body: string) =>
    call("PATCH", `${base(s)}/concepts/${path(id)}`, { frontmatter, body }),
  move: (s: Scope, from_concept_id: string, to_concept_id: string) =>
    call("POST", `${base(s)}/move`, { from_concept_id, to_concept_id }),
  remove: (s: Scope, id: string, force = false) =>
    call<DeleteResult>("DELETE", `${base(s)}/concepts/${path(id)}${force ? "?force=true" : ""}`),
  describeDir: (s: Scope, dir: string, description: string) =>
    call("POST", `${base(s)}/describe`, { dir, description }),
  dirs: (s: Scope) => call<{ dirs: string[] }>("GET", `${base(s)}/dirs`),
  createDir: (s: Scope, dir: string, description: string) =>
    call<{ dir: string }>("POST", `${base(s)}/dirs`, { dir, description }),
  overview: (s: Scope) => call<Overview>("GET", `${base(s)}/overview`),
  reindex: (s: Scope) => call<{ count: number }>("POST", `${base(s)}/reindex`),
  /** Workspace-wide semantic search; `paths` narrows it to those directory subtrees. */
  search: (s: Scope, q: string, paths: string[] = []) =>
    call<Hit[]>("GET", `${base(s)}/search?q=${seg(q)}&top_k=10${paths.map((p) => `&paths=${seg(p)}`).join("")}`),
};
