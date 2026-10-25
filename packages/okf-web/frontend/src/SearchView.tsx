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

  if (error) return <p role="alert" className="error">{error}</p>;
  if (!hits) return <p>Searching…</p>;
  return (
    <article>
      <h1>Search: {q}</h1>
      <p className="muted">Semantic match over directory listings (<code>_index.md</code>).</p>
      {hits.length === 0 && <p>No matches.</p>}
      <ul className="hits">{hits.map((h) => (
        <li key={h.path}>
          <a href={href.dir(h.dir)}>{h.dir || "(root)"}</a> <span className="tag">{h.score.toFixed(2)}</span>
          <pre>{h.excerpt}</pre>
        </li>
      ))}</ul>
    </article>
  );
}
