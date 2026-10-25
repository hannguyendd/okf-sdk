// Test helper: an in-memory stand-in for the okf-web HTTP API.
type Json = Record<string, any>;

export function installFakeApi(opts: { readOnly?: boolean; search?: boolean } = {}) {
  const concepts: Record<string, { frontmatter: Json; body: string }> = {
    "tables/orders": { frontmatter: { type: "table", title: "Orders", tags: ["a"] }, body: "See [users](users.md)\n" },
    "tables/users": { frontmatter: { type: "table", title: "Users" }, body: "Users body" },
  };
  const calls: { method: string; url: string; body?: Json }[] = [];
  const res = (data: unknown, status = 200) =>
    Promise.resolve(new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } }));
  const meta = (id: string) => ({ id, type: concepts[id].frontmatter.type, title: concepts[id].frontmatter.title, description: null, tags: concepts[id].frontmatter.tags ?? [] });

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://x");
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url: url.pathname + url.search, body });
    const p = url.pathname;
    if (p === "/api/info") return res({ location: "/mem", read_only: !!opts.readOnly, search_enabled: !!opts.search });
    if (p === "/api/tree") {
      const dir = url.searchParams.get("dir") ?? "";
      if (dir === "") return res({ dir, description: null, directories: [{ name: "tables", dir: "tables", description: "Warehouse tables" }], concepts: [] });
      return res({ dir, description: "Warehouse tables", directories: [], concepts: Object.keys(concepts).filter((i) => i.startsWith(dir + "/")).map(meta) });
    }
    if (p === "/api/search") {
      if (!opts.search) return res({ error: "embedding is not configured" }, 400);
      return res([{ dir: "tables", path: "tables/_index.md", score: 0.91, excerpt: "Warehouse tables excerpt" }]);
    }
    if (p === "/api/reindex") return res({ action: "reindexed", count: 2, indexes: [] });
    if (p === "/api/describe") return res({ action: "described" });
    if (p === "/api/move") {
      concepts[body!.to_concept_id] = concepts[body!.from_concept_id];
      delete concepts[body!.from_concept_id];
      return res({ action: "moved" });
    }
    if (p === "/api/concepts" && method === "POST") {
      concepts[body!.concept_id] = { frontmatter: body!.frontmatter, body: body!.body };
      return res({ action: "created" }, 201);
    }
    const m = p.match(/^\/api\/concepts\/(.+)$/);
    if (m) {
      const id = decodeURIComponent(m[1]);
      if (!concepts[id]) return res({ error: `concept not found: ${id}` }, 404);
      if (method === "GET") return res({ id, frontmatter: concepts[id].frontmatter, body: concepts[id].body, links_to: id === "tables/orders" ? ["tables/users"] : [] });
      if (method === "PATCH") {
        Object.assign(concepts[id].frontmatter, body!.frontmatter ?? {});
        if (body!.body != null) concepts[id].body = body!.body;
        return res({ action: "updated" });
      }
      if (method === "DELETE") {
        if (id === "tables/users" && url.searchParams.get("force") !== "true") return res({ action: "blocked", referenced_by: ["tables/orders"] });
        delete concepts[id];
        return res({ action: "deleted" });
      }
    }
    return res({ error: "unhandled " + p }, 500);
  }) as typeof fetch;
  return { calls, concepts };
}
