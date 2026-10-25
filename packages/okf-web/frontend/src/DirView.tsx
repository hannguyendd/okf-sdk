import { useEffect, useState } from "react";
import { api, Tree } from "./api";
import { go, href } from "./route";

interface Props { dir: string; readOnly: boolean; version: number; onChanged: () => void; onMessage: (m: string) => void }

export default function DirView({ dir, readOnly, version, onChanged, onMessage }: Props) {
  const [data, setData] = useState<Tree | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null); setError(null);
    api.tree(dir).then(setData, (e) => setError(e.message));
  }, [dir, version]);

  if (error) return <p role="alert" className="error">{error}</p>;
  if (!data) return <p>Loading…</p>;

  const describe = async () => {
    const text = window.prompt("Directory description (empty clears it)", data.description ?? "");
    if (text === null) return;
    try { await api.describe(dir, text); onChanged(); } catch (e) { onMessage((e as Error).message); }
  };

  return (
    <article>
      <h1>{dir || "(root)"}</h1>
      <p className="muted">{data.description ?? "No authored description."}</p>
      {!readOnly && (
        <p className="actions">
          <button onClick={() => go(href.new(dir))}>New concept</button>
          {dir !== "" && <button onClick={describe}>Edit description</button>}
        </p>
      )}
      {data.directories.length > 0 && (
        <section aria-label="Directories">
          <h2>Directories</h2>
          <ul>{data.directories.map((d) => (
            <li key={d.dir}><a href={href.dir(d.dir)}>{d.name}</a>{d.description && <span className="muted"> — {d.description}</span>}</li>
          ))}</ul>
        </section>
      )}
      {data.concepts.length > 0 && (
        <section aria-label="Concepts">
          <h2>Concepts</h2>
          <ul>{data.concepts.map((c) => (
            <li key={c.id}>
              <a href={href.concept(c.id)}>{c.title ?? c.id}</a> <span className="tag">{c.type}</span>
              {c.description && <span className="muted"> — {c.description}</span>}
            </li>
          ))}</ul>
        </section>
      )}
    </article>
  );
}
