import { useCallback, useEffect, useState } from "react";
import { api, BundleInfo, Info } from "./api";
import ConceptForm from "./ConceptForm";
import ConceptView from "./ConceptView";
import DirView from "./DirView";
import { go, href, scopeHref, useRoute } from "./route";
import WorkspaceHome from "./WorkspaceHome";
import SearchView from "./SearchView";
import Tree, { Active } from "./Tree";

export default function App() {
  const { route, scope } = useRoute();
  const [info, setInfo] = useState<Info | null>(null);
  const [version, setVersion] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => { api.info().then(setInfo, (e) => setMessage(e.message)); }, []);
  const changed = useCallback(() => setVersion((v) => v + 1), []);
  const readOnly = info?.read_only ?? true;
  const workspaceMode = info?.mode === "workspace";
  const scopeKey = scope ? `${scope.ws}/${scope.index}` : "";
  const [bundle, setBundle] = useState<BundleInfo | null>(null);
  const loadBundle = useCallback(() => {
    if (!scope) { setBundle(null); return; }
    api.bundleInfo().then(setBundle, (e) => setMessage(e.message));
  }, [scopeKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(loadBundle, [loadBundle]);

  const describeBundle = async () => {
    const text = window.prompt("Index description (empty clears it)", bundle?.description ?? "");
    if (text === null) return;
    try { setBundle(await api.describeBundle(text.trim() ? text : null)); } catch (e) { setMessage((e as Error).message); }
  };

  const reindex = async () => {
    try { const r = await api.reindex(); changed(); setMessage(`Reindexed ${r.count} directory listings.`); }
    catch (e) { setMessage((e as Error).message); }
  };

  const showTree = !workspaceMode || !!scope;
  const active: Active | null =
    route.kind === "concept" || route.kind === "edit" ? { kind: "concept", path: route.id }
    : route.kind === "dir" ? { kind: "dir", path: route.dir }
    : route.kind === "new" ? { kind: "dir", path: route.dir } : null;
  let main;
  if (workspaceMode && !scope) {
    main = <WorkspaceHome readOnly={readOnly} />;
  } else switch (route.kind) {
    case "concept": main = <ConceptView id={route.id} readOnly={readOnly} version={version} onChanged={changed} />; break;
    case "edit": main = <ConceptForm mode="edit" id={route.id} onChanged={changed} />; break;
    case "new": main = <ConceptForm mode="new" dir={route.dir} onChanged={changed} />; break;
    case "search": main = <SearchView q={route.q} />; break;
    default: main = <DirView dir={route.dir} readOnly={readOnly} version={version} onChanged={changed} onMessage={setMessage} />;
  }

  return (
    <div className="grid min-h-screen grid-cols-1 grid-rows-[auto_auto_1fr] md:grid-cols-[280px_1fr]">
      <header className="flex items-center gap-3 border-b border-stone-300 px-4 py-2 md:col-span-2 dark:border-stone-700">
        <a className="font-bold text-stone-900 dark:text-stone-100" href={workspaceMode ? "#/" : href.dir("")}>OKF Memory</a>
        {scope && <a href={scopeHref(scope)}>{`${scope.ws} / ${scope.index}`}</a>}
        {scope && bundle && <span className="truncate text-sm text-stone-500">{bundle.description ?? "No description"}</span>}
        {scope && bundle && !readOnly && <button className="text-xs" onClick={describeBundle}>Edit index description</button>}
        <code title={workspaceMode ? "workspaces location" : "bundle location"} className="flex-1 truncate text-xs text-stone-500">{info?.location}</code>
        {info?.read_only && <span className="rounded-full border border-stone-300 px-2 text-xs text-stone-500 dark:border-stone-700">read-only</span>}
        {showTree && <form role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) go(href.search(q.trim())); }}>
          <input className="w-64" type="search" aria-label="Search" placeholder="Search memory…" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>}
        {!readOnly && (!workspaceMode || scope) && <button onClick={reindex}>Reindex</button>}
      </header>
      {message && <div role="status" className="cursor-pointer bg-sky-100 px-4 py-1.5 md:col-span-2 dark:bg-sky-950" onClick={() => setMessage(null)}>{message}</div>}
      {showTree && <aside className="max-h-[30vh] overflow-auto border-b border-stone-300 p-3 md:max-h-none md:border-r md:border-b-0 dark:border-stone-700"><Tree key={scopeKey} scopeKey={scopeKey} version={version} active={active} /></aside>}
      <main key={scopeKey} className="max-w-4xl px-7 py-4">{main}</main>
    </div>
  );
}
