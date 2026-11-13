import { FormEvent, useState } from "react";
import { Link, Route, Switch, useLocation } from "wouter";
import { useDialogs } from "../components/Dialogs";
import { Logo } from "../components/Logo";
import { ThemeToggle } from "../components/ThemeToggle";
import { Tree } from "../components/Tree";
import { Btn } from "../doodle/Btn";
import { Sketch } from "../doodle/Sketch";
import { Scribble } from "../doodle/Skeleton";
import { api } from "../lib/api";
import { AccentProvider, toneOf } from "../lib/accent";
import { useBundle, useIndexMutation, useInfo, useReadOnly, useWorkspaces } from "../lib/queries";
import { param, to, useScope, workspacePath } from "../lib/scope";
import { ConceptForm } from "./ConceptForm";
import { ConceptPage } from "./ConceptPage";
import { DirPage } from "./DirPage";
import { SearchPage } from "./SearchPage";

/** Header + notebook explorer + the page for one workspace index. */
export function IndexLayout() {
  const scope = useScope();
  const info = useInfo();
  const tone = toneOf(useWorkspaces().data?.find((w) => w.name === scope.ws) ?? { name: scope.ws, color: null });
  const readOnly = useReadOnly();
  const bundle = useBundle();
  const dialogs = useDialogs();
  const [, navigate] = useLocation();
  const [q, setQ] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const describe = useIndexMutation((s, text: string | null) => api.describeBundle(s, text), () => "Noted.");
  const reindex = useIndexMutation((s) => api.reindex(s), (r) => `Tidied up ${r.count} listings.`);

  const editDescription = async () => {
    const text = await dialogs.prompt({ title: "What is this index for?", label: "Index description (empty clears it)", initial: bundle.data?.description ?? "", multiline: true, submitLabel: "Save" });
    if (text === null) return;
    describe.mutate(text.trim() ? text : null, { onError: (e) => setNote(e.message) });
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
          <Link href={`~${workspacePath(scope.ws)}`} className="no-wavy">{scope.ws}</Link> / <Link href="/" className="no-wavy">{scope.index}</Link>
        </span>
        <span className="hidden min-w-24 flex-1 truncate text-ink/70 xl:block" title={bundle.data?.description ?? undefined}>
          {bundle.data ? bundle.data.description ?? "No description" : <Scribble w={220} h={14} />}
        </span>
        {!readOnly && bundle.data && (
          <Btn small tone="pink" tilt={1.5} aria-label="Edit index description" title="Edit index description" onClick={editDescription}>✎</Btn>
        )}
        <form role="search" onSubmit={search} className="ml-auto shrink-0">
          <input type="search" aria-label="Search" placeholder="Search memory…" value={q} onChange={(e) => setQ(e.target.value)} className="field-line w-36 xl:w-44" />
        </form>
        {!info.data
          ? <Scribble w={76} h={26} />
          : readOnly
            ? <span className="font-head text-sm text-ink/60" title="Look, don't touch">read-only</span>
            : <Btn small onClick={runReindex} disabled={reindex.isPending}>Reindex</Btn>}
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
          <Route path="/s/:q">{(p) => <SearchPage q={param(p.q)} />}</Route>
          <Route path="/d/*">{(p) => <DirPage dir={param(p["*"])} />}</Route>
          <Route><DirPage dir="" /></Route>
        </Switch>
      </Sketch>
    </AccentProvider>
  );
}
