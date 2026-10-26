export interface Info { mode: "bundle" | "workspace"; location: string; read_only: boolean; search_enabled: boolean }
export interface DirEntry { name: string; dir: string; description: string | null }
export interface ConceptMeta { id: string; type: string | null; title: string | null; description: string | null; tags: string[] }
export interface Tree { dir: string; description: string | null; directories: DirEntry[]; concepts: ConceptMeta[] }
export interface Concept { id: string; frontmatter: Record<string, unknown>; body: string; links_to: string[] }
export interface Hit { bundle: string; kind: "index" | "bundle"; dir: string; path: string | null; score: number; excerpt: string }
export interface IndexInfo { name: string; description: string | null }
export interface WorkspaceInfo { name: string; indexes: IndexInfo[] }
export interface BundleInfo { workspace: string; bundle: string; description: string | null }
export interface DeleteResult { action: string; referenced_by?: string[] }

import { scopeBase } from "./route";

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
  workspaces: () => call<WorkspaceInfo[]>("GET", "/api/workspaces"),
  createWorkspace: (name: string) => call("POST", "/api/workspaces", { name }),
  createIndex: (ws: string, name: string) =>
    call("POST", `/api/workspaces/${encodeURIComponent(ws)}/indexes`, { name }),
  info: () => call<Info>("GET", "/api/info"),
  tree: (dir: string) => call<Tree>("GET", `${scopeBase()}/tree?dir=${encodeURIComponent(dir)}`),
  get: (id: string) => call<Concept>("GET", `${scopeBase()}/concepts/${enc(id)}`),
  add: (concept_id: string, frontmatter: Record<string, unknown>, body: string) =>
    call("POST", `${scopeBase()}/concepts`, { concept_id, frontmatter, body }),
  patch: (id: string, frontmatter: Record<string, unknown>, body: string) =>
    call("PATCH", `${scopeBase()}/concepts/${enc(id)}`, { frontmatter, body }),
  move: (from_concept_id: string, to_concept_id: string) =>
    call("POST", `${scopeBase()}/move`, { from_concept_id, to_concept_id }),
  remove: (id: string, force = false) =>
    call<DeleteResult>("DELETE", `${scopeBase()}/concepts/${enc(id)}${force ? "?force=true" : ""}`),
  describe: (dir: string, description: string) => call("POST", `${scopeBase()}/describe`, { dir, description }),
  reindex: () => call<{ count: number }>("POST", `${scopeBase()}/reindex`),
  bundleInfo: () => call<BundleInfo>("GET", `${scopeBase()}/bundle`),
  describeBundle: (description: string | null) =>
    call<BundleInfo>("POST", `${scopeBase()}/bundle/describe`, { description }),
  search: (q: string) => call<Hit[]>("GET", `${scopeBase()}/search?q=${encodeURIComponent(q)}&top_k=10`),
};
