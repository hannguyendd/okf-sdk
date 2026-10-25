import { useEffect, useState } from "react";

export type Route =
  | { kind: "dir"; dir: string }
  | { kind: "concept"; id: string }
  | { kind: "new"; dir: string }
  | { kind: "edit"; id: string }
  | { kind: "search"; q: string };

export function parse(hash: string): Route {
  const h = hash.replace(/^#/, "");
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
export const href = {
  dir: (dir: string) => `#/d/${enc(dir)}`,
  concept: (id: string) => `#/c/${enc(id)}`,
  edit: (id: string) => `#/e/${enc(id)}`,
  new: (dir: string) => `#/n/${enc(dir)}`,
  search: (q: string) => `#/s/${encodeURIComponent(q)}`,
};

export const go = (h: string) => { window.location.hash = h; };

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
