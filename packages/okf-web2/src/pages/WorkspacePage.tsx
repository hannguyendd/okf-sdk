import { useQueries } from "@tanstack/react-query";
import { Link } from "wouter";
import { ColorPicker } from "../components/ColorPicker";
import { useDialogs } from "../components/Dialogs";
import { Logo } from "../components/Logo";
import { ThemeToggle } from "../components/ThemeToggle";
import { Pill, Title } from "../components/Title";
import { Btn } from "../doodle/Btn";
import { ErrorNote } from "../doodle/Loading";
import { Okie } from "../doodle/Okie";
import { Scribble } from "../doodle/Skeleton";
import { crayon, scribble, Sketch } from "../doodle/Sketch";
import { AccentProvider, toneOf, useAccent } from "../lib/accent";
import { api, IndexInfo, Overview, Scope, WorkspaceColor } from "../lib/api";
import { keys, useReadOnly, useWorkspaceMutation, useWorkspaces } from "../lib/queries";
import { indexPath, to } from "../lib/scope";
import { ago } from "../lib/time";

const tilts = [-1, 0.7, -0.4, 1.1, -0.8, 0.5];

/**
 * One workspace: every index drawn as a notebook with its stats and latest
 * concepts, plus a "recently remembered" list across all of them.
 */
export function WorkspacePage({ ws }: { ws: string }) {
  const workspaces = useWorkspaces();
  const w = workspaces.data?.find((x) => x.name === ws);
  const readOnly = useReadOnly();
  const dialogs = useDialogs();
  const setColor = useWorkspaceMutation((color: WorkspaceColor) => api.setWorkspaceColor(ws, color));
  const createIndex = useWorkspaceMutation((v: { name: string; description: string }) => api.createIndex(ws, v.name, v.description));

  const indexes = w?.indexes ?? [];
  const overviews = useQueries({
    queries: indexes.map((i) => {
      const s: Scope = { ws, index: i.name };
      return { queryKey: keys.overview(s), queryFn: () => api.overview(s) };
    }),
  });
  const loaded = overviews.every((q) => q.data);
  const total = overviews.reduce((n, q) => n + (q.data?.concepts ?? 0), 0);
  const recent = overviews
    .flatMap((q, i) => (q.data?.recent ?? []).map((r) => ({ ...r, index: indexes[i].name })))
    .sort((a, b) => (b.timestamp ?? "").localeCompare(a.timestamp ?? ""))
    .slice(0, 8);

  const newIndex = async () => {
    const v = await dialogs.form({
      title: `New notebook in ${ws}`,
      submitLabel: "Create",
      fields: [
        { name: "name", label: "Index name", required: true, placeholder: "e.g. payments" },
        { name: "description", label: "What is it for? (optional)", multiline: true },
      ],
    });
    if (v) createIndex.mutate({ name: v.name.trim(), description: v.description });
  };

  if (workspaces.error) return <div className="mx-auto max-w-6xl p-6"><ErrorNote error={workspaces.error} /></div>;
  if (workspaces.data && !w) {
    return (
      <div className="mx-auto max-w-6xl p-6">
        <Logo />
        <p className="mt-6 font-head text-xl">No workspace called “{ws}”. <Link href="~/">Back to workspaces</Link></p>
      </div>
    );
  }

  return (
    <AccentProvider tone={toneOf(w ?? { name: ws, color: null })} className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-center gap-x-5 gap-y-2">
        <Logo />
        <span className="font-head text-lg"><Link href="~/" className="no-wavy">Workspaces</Link> / {ws}</span>
        <span className="flex-1" />
        {!readOnly && w && <ColorPicker name={ws} value={toneOf(w)} chosen={w.color !== null} onPick={(c) => setColor.mutate(c)} />}
        <ThemeToggle />
      </div>

      <Title>{ws}</Title>
      <p className="text-ink/70">
        {w ? `${indexes.length} notebook${indexes.length === 1 ? "" : "s"}` : <Scribble w={120} h={14} className="inline-block" />}
        {w && indexes.length > 0 && (loaded ? ` · ${total} concept${total === 1 ? "" : "s"} remembered` : " · counting…")}
      </p>
      {(setColor.error ?? createIndex.error) && <ErrorNote error={setColor.error ?? createIndex.error} />}
      {!readOnly && <div className="my-4"><Btn tone="green" onClick={newIndex}>New index</Btn></div>}

      {w && indexes.length === 0 && (
        <div className="my-8 flex flex-wrap items-center gap-6">
          <Okie pose="wave" size={180} />
          <p className="font-head text-lg">No notebooks yet. Fine, let’s start one.</p>
        </div>
      )}

      <div className="mt-6 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
        {!w && [0, 1, 2].map((i) => <NotebookSkeleton key={i} tilt={tilts[i]} />)}
        {indexes.map((idx, i) => (
          <NotebookCard key={idx.name} ws={ws} index={idx} overview={overviews[i]?.data} tilt={tilts[i % tilts.length]} />
        ))}
      </div>

      {recent.length > 0 && (
        <section aria-label="Recently remembered" className="mt-12">
          <h2>Recently remembered</h2>
          <Sketch className="mt-2 rotate-[-0.3deg] bg-note px-6 py-3" rough={{ strokeWidth: 1.8 }}>
            <ul className="doodle-list">
              {recent.map((r) => (
                <li key={`${r.index}:${r.id}`}>
                  <Link href={indexPath({ ws, index: r.index }) + to.concept(r.id)}>{r.title ?? r.id}</Link>{" "}
                  {r.type && <Pill>{r.type}</Pill>}{" "}
                  <span className="text-sm text-ink/55">in {r.index} · {ago(r.timestamp)}</span>
                </li>
              ))}
            </ul>
          </Sketch>
        </section>
      )}
    </AccentProvider>
  );
}

/** An index drawn as a spiral notebook: cover in the accent, name label, stats, latest concepts. */
function NotebookCard({ ws, index, overview, tilt }: { ws: string; index: IndexInfo; overview?: Overview; tilt: number }) {
  const accent = useAccent();
  const href = indexPath({ ws, index: index.name });
  const types = Object.entries(overview?.types ?? {}).slice(0, 3);
  return (
    <article aria-label={`Index ${index.name}`} className="relative ml-4 flex" style={{ rotate: `${tilt}deg` }}>
      <Sketch aria-hidden="true" className="absolute! inset-0 translate-x-[-7px] translate-y-[7px]" rough={scribble(accent)} />
      <Sketch className="notebook flex flex-1 flex-col bg-paper" rough={{ strokeWidth: 2.2 }}>
        <div aria-hidden="true" className="spiral" />
        <Sketch className="notebook-label rotate-1" rough={{ stroke: crayon.pink, strokeWidth: 2, strokeLineDash: [6, 5] }}>
          <h3 className="m-0 max-w-full truncate font-head text-lg leading-7 font-bold">
            <Link href={href} className="no-wavy text-ink hover:text-ink">{index.name}</Link>
          </h3>
        </Sketch>
        <p className="line-clamp-2 h-16 text-ink/70">{index.description ?? "No description yet."}</p>
        {overview ? (
          <>
            <p className="h-8 font-head text-sm leading-8">
              {overview.concepts} concept{overview.concepts === 1 ? "" : "s"} · {overview.directories} folder{overview.directories === 1 ? "" : "s"}
            </p>
            <p className="flex h-8 items-center gap-2.5 overflow-hidden">{types.map(([t, n]) => <Pill key={t} count={n}>{t}</Pill>)}</p>
            {overview.recent.length > 0 ? (
              <ul className="m-0 h-24 list-none p-0">
                {overview.recent.slice(0, 3).map((r) => (
                  <li key={r.id} className="h-8 truncate">✎ <Link href={href + to.concept(r.id)} className="no-wavy hover:underline">{r.title ?? r.id}</Link></li>
                ))}
              </ul>
            ) : (
              <p className="line-clamp-3 h-24 text-ink/60">Nothing here yet. Tell me something and I’ll remember it.</p>
            )}
          </>
        ) : (
          <div className="flex h-[192px] flex-col justify-around">
            <Scribble w="45%" h={13} />
            <Scribble w="70%" h={13} />
            <Scribble w="60%" h={13} />
          </div>
        )}
        <div className="mt-auto h-8 text-right font-head">
          <Link href={href}>Open notebook →</Link>
        </div>
      </Sketch>
    </article>
  );
}

function NotebookSkeleton({ tilt }: { tilt: number }) {
  return (
    <div className="ml-4" style={{ rotate: `${tilt}deg` }} aria-hidden="true">
      <Sketch className="notebook flex h-[360px] flex-col justify-around bg-paper text-ink/25" rough={{ stroke: "currentColor", strokeWidth: 2 }}>
        <div className="spiral opacity-40" />
        <Scribble w="60%" h={24} className="mx-auto" />
        <Scribble w="85%" h={13} />
        <Scribble w="50%" h={13} />
        <Scribble w="70%" h={13} />
      </Sketch>
    </div>
  );
}
