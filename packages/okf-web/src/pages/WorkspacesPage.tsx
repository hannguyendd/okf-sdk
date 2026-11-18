import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { useDialogs } from "../components/Dialogs";
import { Logo } from "../components/Logo";
import { ThemeToggle } from "../components/ThemeToggle";
import { Title } from "../components/Title";
import { Btn } from "../doodle/Btn";
import { ErrorNote } from "../doodle/Loading";
import { Okie } from "../doodle/Okie";
import { CardsSkeleton, Scribble } from "../doodle/Skeleton";
import { ColorPicker } from "../components/ColorPicker";
import { scribble, Sketch } from "../doodle/Sketch";
import { toneOf } from "../lib/accent";
import { api, WorkspaceColor } from "../lib/api";
import { keys, usePrefetch, useReadOnly, useWorkspaceMutation, useWorkspaces } from "../lib/queries";
import { workspacePath } from "../lib/scope";

const tilts = [-1.2, 0.8, -0.5, 1.4];

/** Home: every workspace as a sheet of paper; each one is a notebook of folders and concepts. */
export function WorkspacesPage() {
  const { data, error } = useWorkspaces();
  const readOnly = useReadOnly();
  const dialogs = useDialogs();
  const prefetch = usePrefetch();
  const createWs = useWorkspaceMutation((name: string) => api.createWorkspace(name));
  const setColor = useWorkspaceMutation((v: { ws: string; color: WorkspaceColor }) => api.setWorkspaceColor(v.ws, v.color));
  const failed = createWs.error ?? setColor.error;

  const newWorkspace = async () => {
    const name = await dialogs.prompt({ title: "New workspace", label: "Workspace name", required: true, submitLabel: "Create" });
    if (name) createWs.mutate(name);
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="mb-8">
        <div className="flex items-center justify-between"><Logo /><ThemeToggle /></div>
        <p className="mt-1 ml-11 rotate-[-1.5deg] font-head text-lg text-ink/70">OK, fine, I’ll remember it for you.</p>
      </div>
      <Title>Workspaces</Title>
      <p className="text-ink/70">Each workspace is one notebook: folders of concepts, kept as plain markdown.</p>
      {failed && <ErrorNote error={failed} />}
      {!readOnly && <div className="my-4"><Btn tone="green" onClick={newWorkspace}>New workspace</Btn></div>}
      {error && <ErrorNote error={error} />}
      {!data && !error && <CardsSkeleton />}
      {data?.length === 0 && (
        <div className="my-8 flex flex-wrap items-center gap-6">
          <Okie pose="wave" size={180} />
          <p className="font-head text-lg">No workspaces yet. Fine, let’s start one.</p>
        </div>
      )}
      <div className="mt-6 grid gap-8 sm:grid-cols-2">
        {data?.map((w, i) => (
          <Sketch as="section" key={w.name} aria-label={`Workspace ${w.name}`} className="bg-paper px-6 py-4"
            style={{ rotate: `${tilts[i % tilts.length]}deg` }} rough={{ strokeWidth: 2.2 }}>
            {/* notebook-cover strip in the workspace colour */}
            <Sketch aria-hidden="true" className="absolute! -top-1 right-6 left-6 h-4 -rotate-[0.6deg]" rough={{ ...scribble(toneOf(w)), roughness: 2.2 }} />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2><Link href={workspacePath(w.name)}
                onMouseEnter={() => prefetch.workspace({ ws: w.name })}
                onFocus={() => prefetch.workspace({ ws: w.name })}
                className="no-wavy text-ink hover:text-ink">{w.name} <span className="text-base text-ink/50">→</span></Link></h2>
              {!readOnly && <ColorPicker value={toneOf(w)} chosen={w.color !== null} onPick={(color) => setColor.mutate({ ws: w.name, color })} name={w.name} />}
            </div>
            <WorkspaceBlurb ws={w.name} />
          </Sketch>
        ))}
      </div>
    </div>
  );
}

/** The workspace's description (its root directory's), under its name. */
function WorkspaceBlurb({ ws }: { ws: string }) {
  const s = { ws };
  const { data } = useQuery({ queryKey: keys.tree(s, ""), queryFn: () => api.tree(s, "") });
  if (!data) return <Scribble w="60%" h={13} className="my-2" />;
  return <p className="text-ink/60">{data.description ?? "No description yet."}</p>;
}
