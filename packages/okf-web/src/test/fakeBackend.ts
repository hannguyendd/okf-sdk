import { http, HttpResponse } from "msw";

/** In-memory stand-in for the okf-backend API, enough to drive the UI in tests. */
interface FakeConcept { frontmatter: Record<string, unknown>; body: string }
interface FakeWorkspace { color: string | null; descriptions: Record<string, string>; concepts: Record<string, FakeConcept>; dirs: Set<string> }

export interface Call { method: string; path: string; body?: unknown }

export function createBackend(opts: { readOnly?: boolean; search?: boolean } = {}) {
  const workspaces: Record<string, FakeWorkspace> = {
    w: {
      color: null,
      descriptions: { "": "Meeting notes" },
      dirs: new Set(),
      concepts: {
        "tables/orders": { frontmatter: { type: "Table", title: "Orders", timestamp: "2026-11-10T10:00:00Z" }, body: "See [users](users.md)." },
        "tables/users": { frontmatter: { type: "Table", title: "Users", timestamp: "2026-11-12T10:00:00Z" }, body: "People." },
        readme: { frontmatter: { type: "Reference", title: "Readme", timestamp: "2026-11-01T10:00:00Z" }, body: "Hi." },
      },
    },
    empty: { color: null, descriptions: {}, dirs: new Set(), concepts: {} },
  };
  const calls: Call[] = [];

  const json = (data: unknown, status = 200) => HttpResponse.json(data as never, { status });
  const parent = (p: string) => (p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "");
  const dirsOf = (ix: FakeWorkspace) => {
    const all = new Set(ix.dirs);
    for (const id of Object.keys(ix.concepts)) for (let d = parent(id); d; d = parent(d)) all.add(d);
    return all;
  };
  const tree = (ix: FakeWorkspace, dir: string) => ({
    dir,
    description: ix.descriptions[dir] ?? null,
    directories: [...dirsOf(ix)].filter((d) => parent(d) === dir).sort().map((d) => ({ name: d.split("/").pop(), dir: d, description: ix.descriptions[d] ?? null })),
    concepts: Object.entries(ix.concepts).filter(([id]) => parent(id) === dir).map(([id, c]) => ({
      id, type: c.frontmatter.type ?? null, title: c.frontmatter.title ?? null, description: c.frontmatter.description ?? null, tags: c.frontmatter.tags ?? [],
    })),
  });
  const linksTo = (id: string, body: string) =>
    [...body.matchAll(/\]\(([^)]+)\.md\)/g)].map((m) => (parent(id) ? `${parent(id)}/${m[1]}` : m[1]));

  const handler = http.all("/api/*", async ({ request }) => {
    const url = new URL(request.url);
    const path = decodeURIComponent(url.pathname);
    const method = request.method;
    const body = method === "GET" || method === "DELETE" ? undefined : await request.json().catch(() => undefined) as Record<string, any> | undefined;
    calls.push({ method, path: url.pathname + url.search, body });
    const write = method !== "GET";
    if (write && opts.readOnly) return json({ error: "read-only" }, 403);

    if (path === "/api/info") return json({ mode: "workspace", location: "/mem", read_only: !!opts.readOnly, search_enabled: !!opts.search });
    if (path === "/api/workspaces" && method === "GET") {
      return json(Object.entries(workspaces).map(([name, w]) => ({ name, color: w.color })));
    }
    if (path === "/api/workspaces" && method === "POST") {
      workspaces[body!.name] = { color: null, descriptions: {}, dirs: new Set(), concepts: {} };
      return json({ name: body!.name, color: null }, 201);
    }
    let m = path.match(/^\/api\/workspaces\/([^/]+)\/color$/);
    if (m) { workspaces[m[1]].color = body?.color ?? null; return json({ name: m[1], color: workspaces[m[1]].color }); }
    m = path.match(/^\/api\/workspaces\/([^/]+)\/(.*)$/);
    if (!m) return json({ error: "no route" }, 404);
    const ix = workspaces[m[1]];
    if (!ix) return json({ error: `workspace not found: ${m[1]}` }, 404);
    const rest = m[2];

  if (rest === "tree") return json(tree(ix, url.searchParams.get("dir") ?? ""));
    if (rest === "overview") {
      const all = Object.entries(ix.concepts);
      const types: Record<string, number> = {};
      for (const [, c] of all) types[String(c.frontmatter.type)] = (types[String(c.frontmatter.type)] ?? 0) + 1;
      return json({
        concepts: all.length, directories: dirsOf(ix).size, types,
        recent: all.map(([id, c]) => ({ id, title: c.frontmatter.title ?? null, type: c.frontmatter.type ?? null, timestamp: c.frontmatter.timestamp ?? null }))
          .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp))).slice(0, 5),
      });
    }
    if (rest === "search") {
      if (!opts.search) return json({ error: "embedding is not configured" }, 400);
      return json([{ kind: "index", dir: "tables", path: "tables/_index.md", score: 0.91, excerpt: "Orders and users" }]);
    }
    if (rest === "dirs" && method === "GET") return json({ dirs: [...dirsOf(ix)].sort() });
    if (rest === "dirs") {
      if (dirsOf(ix).has(body!.dir)) return json({ error: `directory already exists: ${body!.dir}` }, 400);
      ix.dirs.add(body!.dir);
      return json({ dir: body!.dir, action: "created" }, 201);
    }
    if (rest === "reindex") return json({ action: "reindexed", indexes: [], count: dirsOf(ix).size + 1 });
    if (rest === "describe") {
      if (body!.description) ix.descriptions[body!.dir] = body!.description;
      else delete ix.descriptions[body!.dir];
      return json({ dir: body!.dir, action: "described" });
    }
    if (rest === "move") {
      ix.concepts[body!.to_concept_id] = ix.concepts[body!.from_concept_id];
      delete ix.concepts[body!.from_concept_id];
      return json({ action: "moved" });
    }
    if (rest === "concepts" && method === "POST") {
      if (ix.concepts[body!.concept_id]) return json({ error: "already exists" }, 400);
      ix.concepts[body!.concept_id] = { frontmatter: body!.frontmatter, body: body!.body };
      return json({ action: "created" }, 201);
    }
    const cm = rest.match(/^concepts\/(.+)$/);
    if (cm) {
      const id = cm[1];
      const c = ix.concepts[id];
      if (!c) return json({ error: `not found: ${id}` }, 404);
      if (method === "GET") {
        const linkedFrom = Object.entries(ix.concepts).filter(([o, oc]) => o !== id && linksTo(o, oc.body).includes(id)).map(([o]) => o);
        return json({ id, frontmatter: c.frontmatter, body: c.body, links_to: linksTo(id, c.body), linked_from: linkedFrom });
      }
      if (method === "PATCH") {
        c.frontmatter = { ...c.frontmatter, ...(body!.frontmatter ?? {}) };
        if (body!.body !== undefined) c.body = body!.body;
        return json({ action: "updated" });
      }
      if (method === "DELETE") {
        const refs = Object.entries(ix.concepts).filter(([other, o]) => other !== id && linksTo(other, o.body).includes(id)).map(([other]) => other);
        if (refs.length && url.searchParams.get("force") !== "true") return json({ action: "blocked", referenced_by: refs });
        delete ix.concepts[id];
        return json({ action: "deleted" });
      }
    }
    return json({ error: "no route" }, 404);
  });

  return { handler, workspaces, calls };
}
