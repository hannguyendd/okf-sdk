import { FormEvent, useState } from "react";
import { Link, Route, Switch, useLocation } from "wouter";
import { ColorPicker } from "../components/ColorPicker";
import { useDialogs } from "../components/Dialogs";
import { Logo } from "../components/Logo";
import { ThemeToggle } from "../components/ThemeToggle";
import { Tree } from "../components/Tree";
import { Btn } from "../doodle/Btn";
import { Sketch } from "../doodle/Sketch";
import { Scribble } from "../doodle/Skeleton";
import { api, WorkspaceColor } from "../lib/api";
import { AccentProvider, toneOf } from "../lib/accent";
import { useInfo, useReadOnly, useScopeMutation, useTree, useWorkspaceMutation, useWorkspaces } from "../lib/queries";
import { param, to, useScope } from "../lib/scope";
import { ConceptForm } from "./ConceptForm";
import { ConceptPage } from "./ConceptPage";
import { DirPage } from "./DirPage";
import { SearchPage } from "./SearchPage";
import { WorkspacePage } from "./WorkspacePage";

/** Header + notebook explorer + the page for one workspace. */
export function WorkspaceLayout() {
  const scope = useScope();
  const info = useInfo();
  const workspaces = useWorkspaces();
  const w = workspaces.data?.find((x) => x.name === scope.ws);
  const tone = toneOf(w ?? { name: scope.ws, color: null });
  const readOnly = useReadOnly();
  const root = useTree("");
  const dialogs = useDialogs();
  const [, navigate] = useLocation();
  const [q, setQ] = useState("");
  const [note, setNote] = useState<string | null>(null);
  // the workspace description is its root directory's description
  const describe = useScopeMutation((s, text: string) => api.describeDir(s, "", text), () => "Noted.");
  const reindex = useScopeMutation((s) => api.reindex(s), (r) => `Tidied up ${r.count} listings.`);
  const setColor = useWorkspaceMutation((color: WorkspaceColor) => api.setWorkspaceColor(scope.ws, color));

  if (workspaces.data && !w) {
    return (
      <div className="mx-auto max-w-6xl p-6">
        <Logo />
        <p className="mt-6 font-head text-xl">No workspace called “{scope.ws}”. <Link href="~/">Back to workspaces</Link></p>
      </div>
    );
  }

  const editDescription = async () => {
    const text = await dialogs.prompt({ title: "What is this workspace for?", label: "Workspace description (empty clears it)", initial: root.data?.description ?? "", multiline: true, submitLabel: "Save" });
    if (text === null) return;
    describe.mutate(text.trim(), { onError: (e) => setNote(e.message) });
  };
  const runReindex = () =>
    reindex.mutate(undefined, { onError: (e) => setNote(e.message) });
  const search = (e: FormEvent) => {
    e.preventDefault();
    if (q.trim()) navigate(to.search(q.trim()));
  };

  return (
    <AccentProvider tone={tone} className="mx-auto grid max-w-6xl grid-cols-1 gap-x-8 gap-y-5 px-4 py-5 md:grid-cols-[280px_1fr]">
      <Sketch as="header" className="flex flex-wrap items-center gap-x-5 gap-y-2 bg-paper/90 px-5 py-3 md:col-span-2 lg:flex-nowrap" rough={{ strokeWidth: 2.4 }}>
        <Logo />
        <span className="min-w-0 truncate font-head text-lg whitespace-nowrap text-crumb">
          <Link href="~/" className="no-wavy">Workspaces</Link> / <Link href="/" className="no-wavy">{scope.ws}</Link>
        </span>
        <span className="hidden min-w-24 flex-1 truncate text-ink/70 xl:block" title={root.data?.description ?? undefined}>
          {root.data ? root.data.description ?? "No description" : <Scribble w={220} h={14} />}
        </span>
        {!readOnly && root.data && (
          <Btn small tone="pink" tilt={1.5} aria-label="Edit workspace description" title="Edit workspace description" onClick={editDescription}>✎</Btn>
        )}
        <form role="search" onSubmit={search} className="ml-auto shrink-0">
          <input type="search" aria-label="Search" placeholder="Search memory…" value={q} onChange={(e) => setQ(e.target.value)} className="field-line w-36 xl:w-44" />
        </form>
        {!info.data
          ? <Scribble w={76} h={26} />
          : readOnly
            ? <span className="font-head text-sm text-ink/60" title="Look, don't touch">read-only</span>
            : <Btn small onClick={runReindex} disabled={reindex.isPending}>Reindex</Btn>}
        {!readOnly && w && (
          <ColorPicker name={scope.ws} value={tone} chosen={w.color !== null}
            onPick={(c) => setColor.mutate(c, { onError: (e) => setNote(e.message) })} />
        )}
        <ThemeToggle />
      </Sketch>

      {note && (
        <div role="status" onClick={() => setNote(null)} className="sticky-note justify-self-center md:col-span-2">{note}</div>
      )}

      <aside className="md:sticky md:top-4 md:self-start"><Tree /></aside>

      <Sketch as="main" className="page-sheet min-h-[60vh] min-w-0 bg-paper px-6 py-5 md:px-9" rough={{ strokeWidth: 2.2 }}>
        <span aria-hidden="true" className="tape tape-l" />
        <span aria-hidden="true" className="tape tape-r" />
        <Switch>
          <Route path="/c/*">{(p) => <ConceptPage key={p["*"]} id={param(p["*"])} />}</Route>
          <Route path="/e/*">{(p) => <ConceptForm key={`e:${p["*"]}`} mode="edit" id={param(p["*"])} />}</Route>
          <Route path="/n/*">{(p) => <ConceptForm key={`n:${p["*"]}`} mode="new" dir={param(p["*"])} />}</Route>
          <Route path="/search/:q">{(p) => <SearchPage q={param(p.q)} />}</Route>
          <Route path="/d/*">{(p) => <DirPage dir={param(p["*"])} />}</Route>
          <Route><WorkspacePage /></Route>
        </Switch>
      </Sketch>
    </AccentProvider>
  );
}
