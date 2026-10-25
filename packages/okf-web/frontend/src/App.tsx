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

  useEffect(() => { api.info().then(setInfo, (e) => setMessage(e.message)); }, []);
  const changed = useCallback(() => setVersion((v) => v + 1), []);
  const readOnly = info?.read_only ?? true;

  const reindex = async () => {
    try { const r = await api.reindex(); changed(); setMessage(`Reindexed ${r.count} directory listings.`); }
    catch (e) { setMessage((e as Error).message); }
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
    <div className="app">
      <header>
        <a className="brand" href={href.dir("")}>OKF Memory</a>
        <code title="bundle location">{info?.location}</code>
        {info?.read_only && <span className="tag">read-only</span>}
        <form role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) go(href.search(q.trim())); }}>
          <input type="search" aria-label="Search" placeholder="Search memory…" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        {!readOnly && <button onClick={reindex}>Reindex</button>}
      </header>
      {message && <div role="status" className="status" onClick={() => setMessage(null)}>{message}</div>}
      <aside><Tree version={version} /></aside>
      <main>{main}</main>
    </div>
  );
}
