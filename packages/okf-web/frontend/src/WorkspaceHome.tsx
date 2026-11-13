import { useEffect, useState } from "react";
import { api, WorkspaceInfo } from "./api";
import { scopeHref } from "./route";

export default function WorkspaceHome({ readOnly }: { readOnly: boolean }) {
  const [items, setItems] = useState<WorkspaceInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api.workspaces().then(setItems, (e) => setError(e.message));
  }, [version]);

  const create = async (fn: (name: string) => Promise<unknown>, label: string) => {
    const name = window.prompt(label);
    if (!name) return;
    try { await fn(name); setError(null); setVersion((v) => v + 1); } catch (e) { setError((e as Error).message); }
  };

  if (!items) return error ? <p role="alert" className="text-red-700 dark:text-red-400">{error}</p> : <p>Loading…</p>;
  return (
    <article>
      <h1>Workspaces</h1>
      <p className="text-stone-500">Each workspace holds indexes; each index is one bundle of concepts.</p>
      {error && <p role="alert" className="text-red-700 dark:text-red-400">{error}</p>}
      {!readOnly && (
        <p><button onClick={() => create(api.createWorkspace, "New workspace name")}>New workspace</button></p>
      )}
      {items.length === 0 && <p>No workspaces yet.</p>}
      {items.map((w) => (
        <section key={w.name} aria-label={`Workspace ${w.name}`} className="my-4">
          <h2>{w.name}</h2>
          {w.indexes.length === 0 && <p className="text-stone-500">No indexes.</p>}
          <ul>
            {w.indexes.map((i) => (
              <li key={i.name}>
                <a href={scopeHref({ ws: w.name, index: i.name })}>{i.name}</a>
                {i.description && <span className="text-stone-500"> — {i.description}</span>}
              </li>
            ))}
          </ul>
          {!readOnly && (
            <button aria-label={`New index in ${w.name}`} onClick={() => create((n) => api.createIndex(w.name, n), `New index name in ${w.name}`)}>
              New index
            </button>
          )}
        </section>
      ))}
    </article>
  );
}
