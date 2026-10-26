import { useEffect, useState } from "react";
import { api, Hit } from "./api";
import { href } from "./route";

export default function SearchView({ q }: { q: string }) {
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setHits(null); setError(null);
    api.search(q).then(setHits, (e) => setError(e.message));
  }, [q]);

  if (error) return <p role="alert" className="text-red-700 dark:text-red-400">{error}</p>;
  if (!hits) return <p>Searching…</p>;
  return (
    <article>
      <h1>Search: {q}</h1>
      <p className="text-stone-500">Semantic match over directory listings (<code>_index.md</code>).</p>
      {hits.length === 0 && <p>No matches.</p>}
      <ul className="list-none p-0">{hits.map((h) => (
        <li key={h.path}>
          <a href={href.dir(h.dir)}>{h.dir || "(root)"}</a> <span className="rounded-full border border-stone-300 px-2 text-xs text-stone-500 dark:border-stone-700">{h.score.toFixed(2)}</span>
          <pre className="overflow-auto whitespace-pre-wrap rounded-md bg-stone-200 p-2.5 dark:bg-stone-800">{h.excerpt}</pre>
        </li>
      ))}</ul>
    </article>
  );
}
