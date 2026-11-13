import { createContext, ReactNode, useContext } from "react";
import type { Scope } from "./api";

const ScopeContext = createContext<Scope | null>(null);

export function ScopeProvider({ scope, children }: { scope: Scope; children: ReactNode }) {
  return <ScopeContext.Provider value={scope}>{children}</ScopeContext.Provider>;
}

/** The workspace/index the current page is nested in. */
export function useScope(): Scope {
  const scope = useContext(ScopeContext);
  if (!scope) throw new Error("useScope outside an index route");
  return scope;
}

const enc = (p: string) => p.split("/").map(encodeURIComponent).join("/");

/** Decode a route param; wouter only applies decodeURI, so `%2F` etc. survive. */
export const param = (v: string | undefined) => {
  try { return decodeURIComponent(v ?? ""); } catch { return v ?? ""; }
};

/** Absolute (hash) paths. Pages nested under an index use `to.*` relative paths. */
export const workspacePath = (ws: string) => `/w/${encodeURIComponent(ws)}`;
export const indexPath = (s: Scope) => `/w/${encodeURIComponent(s.ws)}/${encodeURIComponent(s.index)}`;

/** Paths relative to the index route (`<Route path="/w/:ws/:index" nest>`). */
export const to = {
  dir: (dir: string) => (dir ? `/d/${enc(dir)}` : "/"),
  concept: (id: string) => `/c/${enc(id)}`,
  edit: (id: string) => `/e/${enc(id)}`,
  new: (dir: string) => `/n/${enc(dir)}`,
  search: (q: string) => `/s/${encodeURIComponent(q)}`,
};

export const parentDir = (id: string) => (id.includes("/") ? id.slice(0, id.lastIndexOf("/")) : "");
