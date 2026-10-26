import { useCallback, useEffect, useState } from "react";
import { api, Info } from "./api";
import ConceptForm from "./ConceptForm";
import ConceptView from "./ConceptView";
import DirView from "./DirView";
import { go, href, useRoute } from "./route";
import SearchView from "./SearchView";
import Tree from "./Tree";

export default function App() {
  const route = useRoute();
  const [info, setInfo] = useState<Info | null>(null);
  const [version, setVersion] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [q, setQ] = useState("");

  const loadInfo = useCallback(() => { api.info().then(setInfo, (e) => setMessage(e.message)); }, []);
  useEffect(loadInfo, [loadInfo]);
  const changed = useCallback(() => setVersion((v) => v + 1), []);
  const readOnly = info?.read_only ?? true;

  const reindex = async () => {
    try { const r = await api.reindex(); changed(); setMessage(`Reindexed ${r.count} directory listings.`); }
    catch (e) { setMessage((e as Error).message); }
  };

  const describeBundle = async () => {
    const text = window.prompt("Bundle description (empty clears it)", info?.description ?? "");
    if (text === null) return;
    try { await api.describeBundle(text.trim() ? text : null); loadInfo(); } catch (e) { setMessage((e as Error).message); }
  };

  let main;
  switch (route.kind) {
    case "concept": main = <ConceptView id={route.id} readOnly={readOnly} version={version} onChanged={changed} />; break;
    case "edit": main = <ConceptForm mode="edit" id={route.id} onChanged={changed} />; break;
    case "new": main = <ConceptForm mode="new" dir={route.dir} onChanged={changed} />; break;
    case "search": main = <SearchView q={route.q} />; break;
    default: main = <DirView dir={route.dir} readOnly={readOnly} version={version} onChanged={changed} onMessage={setMessage} />;
  }

  return (
    <div className="grid min-h-screen grid-cols-1 grid-rows-[auto_auto_1fr] md:grid-cols-[280px_1fr]">
      <header className="flex items-center gap-3 border-b border-stone-300 px-4 py-2 md:col-span-2 dark:border-stone-700">
        <a className="font-bold text-stone-900 dark:text-stone-100" href={href.dir("")}>OKF Memory</a>
        <div className="flex min-w-0 flex-1 flex-col">
          {info && (
            <div className="flex items-baseline gap-2 truncate text-sm">
              <span className="font-medium">{info.workspace} / {info.bundle}</span>
              <span className="truncate text-stone-500">{info.description ?? "No description"}</span>
              {!readOnly && <button className="text-xs" onClick={describeBundle}>Edit bundle description</button>}
            </div>
          )}
          <code title="bundle location" className="truncate text-xs text-stone-500">{info?.location}</code>
        </div>
        {info?.read_only && <span className="tag">read-only</span>}
        <form role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) go(href.search(q.trim())); }}>
          <input className="w-64" type="search" aria-label="Search" placeholder="Search memory…" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        {!readOnly && <button onClick={reindex}>Reindex</button>}
      </header>
      {message && <div role="status" className="cursor-pointer bg-sky-100 px-4 py-1.5 md:col-span-2 dark:bg-sky-950" onClick={() => setMessage(null)}>{message}</div>}
      <aside className="max-h-[30vh] overflow-auto border-b border-stone-300 p-3 md:max-h-none md:border-r md:border-b-0 dark:border-stone-700"><Tree version={version} /></aside>
      <main className="max-w-4xl px-7 py-4">{main}</main>
    </div>
  );
}
