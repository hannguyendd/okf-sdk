import { useEffect, useState } from "react";

export type Route =
  | { kind: "dir"; dir: string }
  | { kind: "concept"; id: string }
  | { kind: "new"; dir: string }
  | { kind: "edit"; id: string }
  | { kind: "search"; q: string };

/** The workspace index the UI is scoped to (workspace mode), from `#/w/<ws>/<index>/...`. */
export interface Scope { ws: string; index: string }
let current: Scope | null = null;

export const scopeBase = () =>
  current ? `/api/workspaces/${encodeURIComponent(current.ws)}/indexes/${encodeURIComponent(current.index)}` : "/api";

export function parseScope(hash: string): { scope: Scope | null; rest: string } {
  const m = hash.replace(/^#/, "").match(/^\/w\/([^/]+)\/([^/]+)(\/.*)?$/);
  if (!m) return { scope: null, rest: hash.replace(/^#/, "") };
  return { scope: { ws: decodeURIComponent(m[1]), index: decodeURIComponent(m[2]) }, rest: m[3] ?? "" };
}

export function parse(hash: string): Route {
  const h = parseScope(hash).rest;
  const [, kind, ...rest] = h.split("/");
  const tail = rest.map(decodeURIComponent).join("/");
  switch (kind) {
    case "c": return { kind: "concept", id: tail };
    case "e": return { kind: "edit", id: tail };
    case "n": return { kind: "new", dir: tail };
    case "s": return { kind: "search", q: tail };
    default: return { kind: "dir", dir: kind === "d" ? tail : "" };
  }
}

const enc = (p: string) => p.split("/").map(encodeURIComponent).join("/");
export const scopeHref = (s: Scope) => `#/w/${encodeURIComponent(s.ws)}/${encodeURIComponent(s.index)}/`;
const pre = () => (current ? scopeHref(current).slice(0, -1) : "#");
export const href = {
  dir: (dir: string) => `${pre()}/d/${enc(dir)}`,
  concept: (id: string) => `${pre()}/c/${enc(id)}`,
  edit: (id: string) => `${pre()}/e/${enc(id)}`,
  new: (dir: string) => `${pre()}/n/${enc(dir)}`,
  search: (q: string) => `${pre()}/s/${encodeURIComponent(q)}`,
};

export const go = (h: string) => { window.location.hash = h; };

export function useRoute(): { route: Route; scope: Scope | null } {
  const read = () => ({ route: parse(window.location.hash), scope: parseScope(window.location.hash).scope });
  const [state, setState] = useState(read);
  // Set synchronously so hrefs/api calls made while rendering this route use its scope.
  current = state.scope;
  useEffect(() => {
    const on = () => setState(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return state;
}
