/** Typed client for the okf-web HTTP API (`packages/okf-web/src/okf_web/app.py`). */

export interface Info { mode: "workspace"; location: string; read_only: boolean; search_enabled: boolean }
export interface IndexInfo { name: string; description: string | null }
/** Crayon colours a workspace can be tagged with (okf_core.WORKSPACE_COLORS). */
export type WorkspaceColor = "yellow" | "pink" | "green" | "blue" | "red" | "orange" | "purple";
export interface WorkspaceInfo { name: string; color: WorkspaceColor | null; indexes: IndexInfo[] }
export interface DirEntry { name: string; dir: string; description: string | null }
export interface ConceptMeta { id: string; type: string | null; title: string | null; description: string | null; tags: string[] }
export interface Tree { dir: string; description: string | null; directories: DirEntry[]; concepts: ConceptMeta[] }
export interface Concept { id: string; frontmatter: Record<string, unknown>; body: string; links_to: string[]; linked_from?: string[] }
export interface Hit { bundle: string; kind: "index" | "bundle"; dir: string; path: string | null; score: number; excerpt: string }
export interface BundleInfo { workspace: string; bundle: string; description: string | null }
export interface DeleteResult { action: string; referenced_by?: string[] }
export interface Overview {
  concepts: number;
  directories: number;
  types: Record<string, number>;
  recent: { id: string; title: string | null; type: string | null; timestamp: string | null }[];
}

/** The index (bundle) inside a workspace that a request targets. */
export interface Scope { ws: string; index: string }

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
const base = (s: Scope) => `/api/workspaces/${seg(s.ws)}/indexes/${seg(s.index)}`;

export const api = {
  info: () => call<Info>("GET", "/api/info"),
  workspaces: () => call<WorkspaceInfo[]>("GET", "/api/workspaces"),
  createWorkspace: (name: string) => call<WorkspaceInfo>("POST", "/api/workspaces", { name }),
  setWorkspaceColor: (ws: string, color: WorkspaceColor | null) =>
    call<{ name: string; color: WorkspaceColor | null }>("POST", `/api/workspaces/${seg(ws)}/color`, { color }),
  createIndex: (ws: string, name: string, description?: string) =>
    call<IndexInfo>("POST", `/api/workspaces/${seg(ws)}/indexes`, { name, description: description || undefined }),

  bundle: (s: Scope) => call<BundleInfo>("GET", `${base(s)}/bundle`),
  describeBundle: (s: Scope, description: string | null) =>
    call<BundleInfo>("POST", `${base(s)}/bundle/describe`, { description }),
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
  search: (s: Scope, q: string) => call<Hit[]>("GET", `${base(s)}/search?q=${seg(q)}&top_k=10`),
};
