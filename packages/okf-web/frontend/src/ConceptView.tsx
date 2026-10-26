import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { api, Concept } from "./api";
import { go, href } from "./route";

interface Props { id: string; readOnly: boolean; version: number; onChanged: () => void }

/** Rewrite relative `.md` links in a concept body to in-app routes. */
function resolve(id: string, target: string): string | null {
  if (/^[a-z]+:/i.test(target) || !target.endsWith(".md")) return null;
  const parts = id.split("/").slice(0, -1);
  for (const seg of target.replace(/\.md$/, "").split("/")) {
    if (seg === "..") parts.pop(); else if (seg !== "." && seg !== "") parts.push(seg);
  }
  return href.concept(parts.join("/"));
}

export default function ConceptView({ id, readOnly, version, onChanged }: Props) {
  const [concept, setConcept] = useState<Concept | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<string[] | null>(null);

  useEffect(() => {
    setConcept(null); setError(null); setBlocked(null);
    api.get(id).then(setConcept, (e) => setError(e.message));
  }, [id, version]);

  if (error) return <p role="alert" className="text-red-700 dark:text-red-400">{error}</p>;
  if (!concept) return <p>Loading…</p>;

  const fail = (e: unknown) => setError((e as Error).message);
  const dir = id.includes("/") ? id.slice(0, id.lastIndexOf("/")) : "";
  const { title, ...rest } = concept.frontmatter;

  const move = async () => {
    const to = window.prompt("Move to concept id", id);
    if (!to || to === id) return;
    try { await api.move(id, to); onChanged(); go(href.concept(to)); } catch (e) { fail(e); }
  };
  const remove = async (force: boolean) => {
    if (!force && !window.confirm(`Delete ${id}?`)) return;
    try {
      const r = await api.remove(id, force);
      if (r.action === "blocked") { setBlocked(r.referenced_by ?? []); return; }
      onChanged(); go(href.dir(dir));
    } catch (e) { fail(e); }
  };

  return (
    <article>
      <h1>{String(title ?? id)}</h1>
      <p className="text-stone-500"><code>{id}</code></p>
      {!readOnly && (
        <p className="flex gap-2">
          <button onClick={() => go(href.edit(id))}>Edit</button>
          <button onClick={move}>Move</button>
          <button className="text-red-700 dark:text-red-400" onClick={() => remove(false)}>Delete</button>
        </p>
      )}
      {blocked && (
        <div role="alert" className="text-red-700 dark:text-red-400">
          Referenced by: {blocked.join(", ")}.{" "}
          <button className="text-red-700 dark:text-red-400" onClick={() => remove(true)}>Delete anyway</button>
        </div>
      )}
      <table className="my-3 border-collapse"><tbody>
        {Object.entries(rest).map(([k, v]) => (
          <tr key={k}><th className="py-0.5 pr-4 text-left align-top font-medium text-stone-500">{k}</th><td>{typeof v === "string" ? v : JSON.stringify(v)}</td></tr>
        ))}
      </tbody></table>
      <div className="body border-t border-stone-300 pt-2 dark:border-stone-700 [&_h1]:my-3 [&_h1]:text-2xl [&_h1]:font-bold [&_h2]:my-3 [&_h2]:text-xl [&_h2]:font-semibold [&_p]:my-2 [&_pre]:overflow-auto [&_pre]:rounded-md [&_pre]:bg-stone-200 [&_pre]:p-2.5 dark:[&_pre]:bg-stone-800 [&_ul]:list-disc [&_ul]:pl-6">
        <Markdown components={{ a: ({ href: h, children }) => <a href={resolve(id, h ?? "") ?? h}>{children}</a> }}>
          {concept.body}
        </Markdown>
      </div>
      {concept.links_to.length > 0 && (
        <section aria-label="Links to">
          <h2>Links to</h2>
          <ul>{concept.links_to.map((l) => <li key={l}><a href={href.concept(l)}>{l}</a></li>)}</ul>
        </section>
      )}
    </article>
  );
}
