import { DragEvent, KeyboardEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { Link, useLocation } from "wouter";
import { DoodleIcon } from "../doodle/DoodleIcon";
import { ErrorNote } from "../doodle/Loading";
import { TreeSkeleton } from "../doodle/Skeleton";
import { crayon, scribble, Sketch } from "../doodle/Sketch";
import { api, ConceptMeta, DirEntry } from "../lib/api";
import { useAccent } from "../lib/accent";
import { useIndexMutation, usePrefetch, useReadOnly, useTree } from "../lib/queries";
import { param, parentDir, to, useScope } from "../lib/scope";

interface Active { kind: "dir" | "concept"; path: string }

/** What the current (index-relative) location points at, for highlighting. */
function useActive(): Active | null {
  const [loc] = useLocation();
  const m = loc.match(/^\/([cedn])\/(.*)$/);
  if (!m) return loc === "/" ? { kind: "dir", path: "" } : null;
  const path = param(m[2]);
  return m[1] === "c" || m[1] === "e" ? { kind: "concept", path } : { kind: "dir", path };
}

const ancestors = (path: string) => {
  const parts = path.split("/").filter(Boolean);
  return parts.map((_, i) => parts.slice(0, i + 1).join("/"));
};

const FolderIcon = ({ open }: { open: boolean }) => (
  <svg aria-hidden="true" viewBox="0 0 32 32" className="size-6 shrink-0" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9c0-2 1-3 3-3h6l3 3h11c2 0 3 1 3 3v12c0 2-1 3-3 3H6c-2 0-3-1-3-3z" fill={crayon.pink} fillOpacity=".85" />
    {open && <path d="M3 15c5-1 18-2 26 0" />}
  </svg>
);
const PageIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 32 32" className="size-6 shrink-0" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M8 3h11l6 6v19c0 1-1 2-2 2H8c-1 0-2-1-2-2V5c0-1 1-2 2-2z" fill={crayon.green} fillOpacity=".6" />
    <path d="M19 3v6h6M10 16c3-1 7 1 11-1M10 21c3 1 7-1 10 0" />
  </svg>
);

/** Crayon highlight behind the open page's row, in the workspace accent; one row tall. */
function CurrentMark() {
  return (
    <Sketch as="span" aria-hidden="true" pad={0} className="crayon-fill absolute! inset-x-0 inset-y-1 -z-10 block"
      rough={{ ...scribble(useAccent()), stroke: "none", hachureGap: 3.5, fillWeight: 3 }} />
  );
}

interface Ctx {
  open: Set<string>;
  toggle: (dir: string) => void;
  active: Active | null;
  /** Move a dragged concept into `dir` ("" = root); undefined when read-only. */
  drop?: (conceptId: string, dir: string) => void;
}

const DRAG_TYPE = "application/x-okf-concept";

/** Drop-target props + highlight state for a folder row (or the root label). */
function useDropTarget(dir: string, drop: Ctx["drop"]) {
  const [over, setOver] = useState(false);
  if (!drop) return { over: false, props: {} };
  const accepts = (e: DragEvent) => e.dataTransfer.types.includes(DRAG_TYPE);
  return {
    over,
    props: {
      onDragOver: (e: DragEvent) => { if (accepts(e)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setOver(true); } },
      onDragLeave: () => setOver(false),
      onDrop: (e: DragEvent) => {
        setOver(false);
        const id = e.dataTransfer.getData(DRAG_TYPE);
        if (id) { e.preventDefault(); drop(id, dir); }
      },
    },
  };
}

function ConceptRow({ c, dir, active, draggable }: { c: ConceptMeta; dir: string; active: Active | null; draggable: boolean }) {
  const cur = active?.kind === "concept" && active.path === c.id;
  const scope = useScope();
  const prefetch = usePrefetch();
  const warm = () => prefetch.concept(scope, c.id);
  return (
    <li role="treeitem" aria-selected={cur} className="pl-6">
      <Link href={to.concept(c.id)} title={c.description ?? c.id} data-kind="concept" data-dir={dir}
        aria-current={cur ? "page" : undefined} className="tree-link" onMouseEnter={warm} onFocus={warm}
        draggable={draggable}
        onDragStart={(e: DragEvent) => { e.dataTransfer.setData(DRAG_TYPE, c.id); e.dataTransfer.effectAllowed = "move"; }}>
        <DoodleIcon name="page" fallback={<PageIcon />} />
        {cur && <CurrentMark />}
        <span className="min-w-0 truncate">{c.title ?? c.id.split("/").pop()}</span>
      </Link>
    </li>
  );
}

function DirNode({ d, ctx }: { d: DirEntry; ctx: Ctx }) {
  const isOpen = ctx.open.has(d.dir);
  const scope = useScope();
  const prefetch = usePrefetch();
  const warm = () => prefetch.dir(scope, d.dir);
  const cur = ctx.active?.kind === "dir" && ctx.active.path === d.dir;
  const target = useDropTarget(d.dir, ctx.drop);
  return (
    <li role="treeitem" aria-expanded={isOpen} aria-selected={cur}>
      <div className={`flex items-center rounded-lg ${target.over ? "drop-target" : ""}`} {...target.props}>
        <button aria-label={`Toggle ${d.name}`} tabIndex={-1} onClick={() => ctx.toggle(d.dir)} onMouseEnter={warm}
          className="grid h-8 w-6 shrink-0 cursor-pointer place-items-center text-ink/60 hover:text-ink">
          <span className={`inline-block transition-transform ${isOpen ? "rotate-90" : ""}`}>➜</span>
        </button>
        <Link href={to.dir(d.dir)} title={d.description ?? d.dir} data-kind="dir" data-dir={d.dir}
          aria-current={cur ? "page" : undefined} className="tree-link" onMouseEnter={warm} onFocus={warm}>
          <DoodleIcon name={isOpen ? "folder-open" : "folder-closed"} fallback={<FolderIcon open={isOpen} />} />
          {cur && <CurrentMark />}
          <span className="min-w-0 truncate">{d.name}</span>
        </Link>
      </div>
      {isOpen && <Children dir={d.dir} ctx={ctx} />}
    </li>
  );
}

function Children({ dir, ctx }: { dir: string; ctx: Ctx }) {
  const { data, error } = useTree(dir);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <div className="pl-6"><TreeSkeleton rows={2} /></div>;
  const empty = data.directories.length + data.concepts.length === 0;
  return (
    <ul role="group" className="tree-branch">
      {data.directories.map((d) => <DirNode key={d.dir} d={d} ctx={ctx} />)}
      {data.concepts.map((c) => <ConceptRow key={c.id} c={c} dir={dir} active={ctx.active} draggable={!!ctx.drop} />)}
      {empty && <li className="h-8 pl-6 text-sm text-ink/50">nothing yet</li>}
    </ul>
  );
}

const storeKey = (ws: string, index: string) => `okf-tree:${ws}/${index}`;
const loadOpen = (k: string): string[] => {
  try { return JSON.parse(localStorage.getItem(k) ?? "[]"); } catch { return []; }
};

/**
 * The explorer, drawn as an open spiral notebook with a name label. Lazy:
 * a directory's children load when it is opened. Expanded directories persist
 * per index; the active page's ancestors open automatically; arrow keys move.
 */
export function Tree() {
  const scope = useScope();
  const key = storeKey(scope.ws, scope.index);
  const [open, setOpen] = useState(() => new Set(loadOpen(key)));
  const active = useActive();
  const root = useTree("");

  const update = (fn: (s: Set<string>) => Set<string>) =>
    setOpen((prev) => {
      const next = fn(prev);
      try { localStorage.setItem(key, JSON.stringify([...next])); } catch { /* storage unavailable */ }
      return next;
    });
  const toggle = (dir: string) => update((s) => { const n = new Set(s); if (n.has(dir)) n.delete(dir); else n.add(dir); return n; });

  useEffect(() => {
    if (!active) return;
    const need = ancestors(active.kind === "dir" ? active.path : parentDir(active.path));
    if (need.some((p) => !open.has(p))) update((s) => new Set([...s, ...need]));
  }, [active?.kind, active?.path]); // eslint-disable-line react-hooks/exhaustive-deps

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    const t = e.target as HTMLElement;
    if (!(t instanceof HTMLAnchorElement) || !t.dataset.kind) return;
    const links = [...e.currentTarget.querySelectorAll<HTMLAnchorElement>("a[data-kind]")];
    const i = links.indexOf(t);
    const focus = (el?: HTMLElement) => { if (el) { e.preventDefault(); el.focus(); } };
    const dir = t.dataset.dir ?? "";
    const isDir = t.dataset.kind === "dir";
    if (e.key === "ArrowDown") focus(links[i + 1]);
    else if (e.key === "ArrowUp") focus(links[i - 1]);
    else if (e.key === "ArrowRight" && isDir) { e.preventDefault(); if (!open.has(dir)) toggle(dir); else focus(links[i + 1]); }
    else if (e.key === "ArrowLeft") {
      e.preventDefault();
      if (isDir && open.has(dir)) toggle(dir);
      else focus(links.find((l) => l.dataset.kind === "dir" && l.dataset.dir === (isDir ? parentDir(dir) : dir)));
    }
  };

  const accent = useAccent();
  const readOnly = useReadOnly();
  const [loc, navigate] = useLocation();
  const move = useIndexMutation(
    (s, v: { from: string; to: string }) => api.move(s, v.from, v.to),
    (_, v) => `Moved it to ${parentDir(v.to) || "the front page"}. Links are fixed, you’re welcome.`,
  );
  const drop = (id: string, dir: string) => {
    const dest = dir ? `${dir}/${id.split("/").pop()}` : id.split("/").pop()!;
    if (dest === id) return;
    move.mutate({ from: id, to: dest }, {
      onSuccess: () => {
        if (dir) update((s) => new Set([...s, ...ancestors(dir)]));
        if (loc === to.concept(id)) navigate(to.concept(dest));
      },
      onError: (e) => toast(`Oops, I dropped my crayons: ${e.message}`),
    });
  };
  const ctx: Ctx = { open, toggle, active, drop: readOnly ? undefined : drop };
  const rootTarget = useDropTarget("", ctx.drop);
  const atRoot = active?.kind === "dir" && active.path === "";
  return (
    <nav aria-label="Bundle tree" onKeyDown={onKeyDown} className="relative ml-5 mb-6">
      {/* the notebook's cover, peeking out behind the page */}
      <Sketch aria-hidden="true" className="absolute! inset-0 translate-x-[-8px] translate-y-[8px] -rotate-1" rough={scribble(accent)} />
      <Sketch className="notebook -rotate-[0.6deg] bg-paper" rough={{ strokeWidth: 2.2 }}>
        <div aria-hidden="true" className="spiral" />
        {/* the name label doubles as the way back to the front page (and a drop target for it) */}
        <div className="relative">
          <Sketch className={`notebook-label rotate-1 ${rootTarget.over ? "drop-target" : ""}`} {...rootTarget.props}
            rough={{ stroke: crayon.pink, strokeWidth: 2, strokeLineDash: [6, 5] }}>
            <Link href={to.dir("")} aria-current={atRoot ? "page" : undefined}
              title={ctx.drop ? "Open the front page · drop a page here to move it to the front" : "Open the front page"}
              className={`no-wavy flex size-full min-w-0 flex-col items-center justify-center rounded-md pr-9 pl-2 text-ink no-underline hover:bg-[var(--hover)] ${atRoot ? "bg-[var(--hover)]" : ""}`}>
              <span className="flex max-w-full items-center gap-1.5 font-head text-base font-bold">
                <DoodleIcon name="notebook" size={22} fallback={<span aria-hidden="true">📒</span>} />
                <span className="min-w-0 truncate">{scope.index}</span>
              </span>
              <span className="text-xs text-ink/55">{rootTarget.over ? "drop it on the front page" : "front page"}</span>
            </Link>
          </Sketch>
          {open.size > 0 && (
            <button aria-label="Fold all folders" title="Fold all folders" onClick={() => update(() => new Set())}
              className="absolute top-6 right-2 grid size-8 -translate-y-1/2 cursor-pointer place-items-center rounded-full text-ink/60 hover:bg-[var(--hover)] hover:text-ink">
              {/* two chevrons squeezing together: fold everything up */}
              <svg aria-hidden="true" viewBox="0 0 20 20" className="size-5 fill-none stroke-current" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 3.5l5 4.5 5-4.5M5 16.5l5-4.5 5 4.5" />
              </svg>
            </button>
          )}
        </div>
        {root.error && <ErrorNote error={root.error} />}
        {!root.data && !root.error && <TreeSkeleton />}
        {root.data && (
          <ul role="tree" className="m-0 list-none p-0">
            {root.data.directories.map((d) => <DirNode key={d.dir} d={d} ctx={ctx} />)}
            {root.data.concepts.map((c) => <ConceptRow key={c.id} c={c} dir="" active={active} draggable={!!ctx.drop} />)}
            {root.data.directories.length + root.data.concepts.length === 0 && (
              <li className="px-1 text-sm text-ink/50">This notebook is empty.</li>
            )}
          </ul>
        )}
      </Sketch>
    </nav>
  );
}
