import { KeyboardEvent, ReactNode, useEffect, useState } from "react";
import { api, Tree as TreeData } from "./api";
import { href } from "./route";

export interface Active { kind: "dir" | "concept"; path: string }

const icon = (children: ReactNode, cls = "") => (
  <svg aria-hidden="true" viewBox="0 0 16 16" className={`size-4 shrink-0 fill-none stroke-current stroke-[1.4] ${cls}`} strokeLinecap="round" strokeLinejoin="round">{children}</svg>
);
const Chevron = ({ open }: { open: boolean }) =>
  icon(<path d="M6 4l4 4-4 4" />, `transition-transform ${open ? "rotate-90" : ""}`);
const Folder = ({ open }: { open: boolean }) =>
  icon(open ? <path d="M1.5 4.5v8h11l2-6h-11l-2 6M1.5 4.5v-1h4l1.5 1.5h5v1.5" /> : <path d="M1.5 3.5h4l1.5 1.5h7.5v7.5h-13z" />, "text-amber-600 dark:text-amber-400");
const Doc = () => icon(<path d="M4 1.5h5l3 3v10H4zM9 1.5v3h3M6 8h4M6 10.5h4" />, "text-stone-500");

const ancestors = (path: string) => {
  const parts = path.split("/").filter(Boolean);
  return parts.map((_, i) => parts.slice(0, i + 1).join("/"));
};
const parentOf = (path: string) => path.split("/").slice(0, -1).join("/");

const rowCls = (active: boolean) =>
  `flex items-center gap-1 rounded-md py-0.5 pr-2 text-sm hover:bg-stone-200/70 dark:hover:bg-stone-800 ${
    active ? "bg-sky-100 font-medium dark:bg-sky-950" : ""
  }`;
const linkCls = (active: boolean) =>
  `flex min-w-0 flex-1 items-center gap-1.5 truncate hover:no-underline ${
    active ? "text-sky-800 dark:text-sky-300" : "text-stone-800 dark:text-stone-200"
  }`;

interface NodeProps {
  dir: string;
  name: string;
  description?: string | null;
  open: Set<string>;
  toggle: (dir: string) => void;
  active: Active | null;
  version: number;
}

function Node({ dir, name, description, open, toggle, active, version }: NodeProps) {
  const isOpen = open.has(dir);
  const [data, setData] = useState<TreeData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    api.tree(dir).then((d) => { setData(d); setError(null); }, (e) => setError(e.message));
  }, [isOpen, dir, version]);

  const current = active?.kind === "dir" && active.path === dir;
  return (
    <li role="treeitem" aria-expanded={isOpen} aria-selected={current}>
      <div className={rowCls(current)}>
        <button aria-label={`Toggle ${name}`} aria-expanded={isOpen} tabIndex={-1} onClick={() => toggle(dir)}
          className="!border-0 !p-0.5 text-stone-500 hover:text-stone-900 dark:hover:text-stone-100">
          <Chevron open={isOpen} />
        </button>
        <a href={href.dir(dir)} title={description ?? dir} data-kind="dir" data-dir={dir} aria-current={current ? "page" : undefined} className={linkCls(current)}>
          <Folder open={isOpen} /><span className="truncate">{name}</span>
        </a>
      </div>
      {isOpen && error && <p className="ml-6 text-xs text-red-700 dark:text-red-400">{error}</p>}
      {isOpen && data && (
        <ul role="group" className="ml-[11px] list-none border-l border-stone-300 pl-1.5 dark:border-stone-600">
          {data.directories.map((d) => (
            <Node key={d.dir} dir={d.dir} name={d.name} description={d.description} open={open} toggle={toggle} active={active} version={version} />
          ))}
          {data.concepts.map((c) => {
            const cur = active?.kind === "concept" && active.path === c.id;
            return (
              <li key={c.id} role="treeitem" aria-selected={cur} className="pl-[22px]">
                <div className={rowCls(cur)}>
                  <a href={href.concept(c.id)} title={c.description ?? c.id} data-kind="concept" data-dir={dir} aria-current={cur ? "page" : undefined} className={linkCls(cur)}>
                    <Doc /><span className="truncate">{c.title ?? c.id.split("/").pop()}</span>
                  </a>
                </div>
              </li>
            );
          })}
          {data.directories.length + data.concepts.length === 0 && (
            <li className="py-0.5 pl-[22px] text-xs text-stone-500">empty</li>
          )}
        </ul>
      )}
    </li>
  );
}

const storeKey = (scopeKey: string) => `okf-tree:${scopeKey}`;
function load(scopeKey: string): string[] {
  try { return JSON.parse(localStorage.getItem(storeKey(scopeKey)) ?? "[]"); } catch { return []; }
}

/**
 * Lazy explorer-style tree. Expanded directories persist per index, the open
 * concept/directory is revealed and highlighted, and arrow keys navigate.
 * `version` bumps force every open node to refetch after a write.
 */
export default function Tree({ version, active, scopeKey }: { version: number; active: Active | null; scopeKey: string }) {
  const [open, setOpen] = useState(() => new Set(load(scopeKey)));
  const [rootData, setRootData] = useState<TreeData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const update = (fn: (s: Set<string>) => Set<string>) =>
    setOpen((prev) => {
      const next = fn(prev);
      try { localStorage.setItem(storeKey(scopeKey), JSON.stringify([...next])); } catch { /* storage unavailable */ }
      return next;
    });
  const toggle = (dir: string) => update((s) => { const n = new Set(s); n.has(dir) ? n.delete(dir) : n.add(dir); return n; });

  // Reveal the active item: open every ancestor directory.
  useEffect(() => {
    if (!active) return;
    const need = active.kind === "dir" ? ancestors(active.path) : ancestors(parentOf(active.path));
    if (need.some((p) => !open.has(p))) update((s) => new Set([...s, ...need]));
  }, [active?.kind, active?.path]);

  useEffect(() => {
    api.tree("").then((d) => { setRootData(d); setError(null); }, (e) => setError(e.message));
  }, [version]);

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    const target = e.target as HTMLElement;
    if (!(target instanceof HTMLAnchorElement) || !target.dataset.kind) return;
    const links = [...e.currentTarget.querySelectorAll<HTMLAnchorElement>("a[data-kind]")];
    const i = links.indexOf(target);
    const focus = (el?: HTMLElement | null) => { if (el) { e.preventDefault(); el.focus(); } };
    const isDir = target.dataset.kind === "dir";
    const dir = target.dataset.dir ?? "";
    switch (e.key) {
      case "ArrowDown": focus(links[i + 1]); break;
      case "ArrowUp": focus(links[i - 1]); break;
      case "ArrowRight":
        if (!isDir) break;
        e.preventDefault();
        if (!open.has(dir)) toggle(dir); else focus(links[i + 1]);
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (isDir && open.has(dir)) toggle(dir);
        else focus(links.find((l) => l.dataset.kind === "dir" && l.dataset.dir === (isDir ? parentOf(dir) : dir)));
        break;
    }
  };

  return (
    <nav aria-label="Bundle tree" onKeyDown={onKeyDown}>
      <div className="mb-1 flex items-center justify-between px-1 text-xs font-semibold uppercase tracking-wide text-stone-500">
        <span>Explorer</span>
        <button aria-label="Collapse all" title="Collapse all" className="!border-0 !p-0.5 hover:text-stone-900 dark:hover:text-stone-100"
          onClick={() => update(() => new Set())}>
          {icon(<path d="M3 6l5-3.5L13 6M3 10l5 3.5 5-3.5" />)}
        </button>
      </div>
      {error && <p className="text-xs text-red-700 dark:text-red-400">{error}</p>}
      {rootData && (
        <ul role="tree" className="m-0 list-none p-0">
          {rootData.directories.map((d) => (
            <Node key={d.dir} dir={d.dir} name={d.name} description={d.description} open={open} toggle={toggle} active={active} version={version} />
          ))}
          {rootData.concepts.map((c) => {
            const cur = active?.kind === "concept" && active.path === c.id;
            return (
              <li key={c.id} role="treeitem" aria-selected={cur} className="pl-[22px]">
                <div className={rowCls(cur)}>
                  <a href={href.concept(c.id)} title={c.id} data-kind="concept" data-dir="" aria-current={cur ? "page" : undefined} className={linkCls(cur)}>
                    <Doc /><span className="truncate">{c.title ?? c.id}</span>
                  </a>
                </div>
              </li>
            );
          })}
          {rootData.directories.length + rootData.concepts.length === 0 && (
            <li className="px-1 py-0.5 text-xs text-stone-500">This bundle is empty.</li>
          )}
        </ul>
      )}
    </nav>
  );
}
