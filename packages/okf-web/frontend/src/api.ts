export interface Info {
  location: string; read_only: boolean; search_enabled: boolean;
  workspace: string; bundle: string; description: string | null;
}
export interface DirEntry { name: string; dir: string; description: string | null }
export interface ConceptMeta { id: string; type: string | null; title: string | null; description: string | null; tags: string[] }
export interface Tree { dir: string; description: string | null; directories: DirEntry[]; concepts: ConceptMeta[] }
export interface Concept { id: string; frontmatter: Record<string, unknown>; body: string; links_to: string[] }
export interface Hit { bundle: string; kind: "index" | "bundle"; dir: string; path: string | null; score: number; excerpt: string }
export interface DeleteResult { action: string; referenced_by?: string[] }

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

const enc = (id: string) => id.split("/").map(encodeURIComponent).join("/");

export const api = {
  info: () => call<Info>("GET", "/api/info"),
  tree: (dir: string) => call<Tree>("GET", `/api/tree?dir=${encodeURIComponent(dir)}`),
  get: (id: string) => call<Concept>("GET", `/api/concepts/${enc(id)}`),
  add: (concept_id: string, frontmatter: Record<string, unknown>, body: string) =>
    call("POST", "/api/concepts", { concept_id, frontmatter, body }),
  patch: (id: string, frontmatter: Record<string, unknown>, body: string) =>
    call("PATCH", `/api/concepts/${enc(id)}`, { frontmatter, body }),
  move: (from_concept_id: string, to_concept_id: string) =>
    call("POST", "/api/move", { from_concept_id, to_concept_id }),
  remove: (id: string, force = false) =>
    call<DeleteResult>("DELETE", `/api/concepts/${enc(id)}${force ? "?force=true" : ""}`),
  describe: (dir: string, description: string) => call("POST", "/api/describe", { dir, description }),
  reindex: () => call<{ count: number }>("POST", "/api/reindex"),
  describeBundle: (description: string | null) =>
    call<{ workspace: string; bundle: string; description: string | null }>("POST", "/api/bundle/describe", { description }),
  search: (q: string) => call<Hit[]>("GET", `/api/search?q=${encodeURIComponent(q)}&top_k=10`),
};
