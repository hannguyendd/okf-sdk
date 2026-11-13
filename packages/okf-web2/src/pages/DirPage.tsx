import { Link, useLocation } from "wouter";
import { Crumbs } from "../components/Crumbs";
import { useDialogs } from "../components/Dialogs";
import { Pill, Title } from "../components/Title";
import { Btn } from "../doodle/Btn";
import { ErrorNote } from "../doodle/Loading";
import { Okie } from "../doodle/Okie";
import { PageSkeleton } from "../doodle/Skeleton";
import { api } from "../lib/api";
import { useIndexMutation, useReadOnly, useTree } from "../lib/queries";
import { parentDir, to, useScope } from "../lib/scope";

export function DirPage({ dir }: { dir: string }) {
  const scope = useScope();
  const { data, error } = useTree(dir);
  const readOnly = useReadOnly();
  const dialogs = useDialogs();
  const [, navigate] = useLocation();
  const describe = useIndexMutation((s, text: string) => api.describeDir(s, dir, text), () => "Noted.");
  const mkdir = useIndexMutation((s, v: { name: string; description: string }) =>
    api.createDir(s, dir ? `${dir}/${v.name.trim()}` : v.name.trim(), v.description), () => "Folder’s ready. Fill it whenever.");

  if (error) return <ErrorNote error={error} />;
  if (!data) return <PageSkeleton />;

  const editDescription = async () => {
    const text = await dialogs.prompt({ title: `Describe ${dir}`, label: "Directory description (empty clears it)", initial: data.description ?? "", multiline: true, submitLabel: "Save" });
    if (text !== null) describe.mutate(text);
  };

  const newFolder = async () => {
    const v = await dialogs.form({
      title: dir ? `New folder in ${dir}` : "New folder",
      submitLabel: "Create",
      fields: [
        { name: "name", label: "Folder name", required: true, placeholder: "e.g. playbooks", hint: "Letters, numbers, - _ . (use / for nested folders)" },
        { name: "description", label: "What goes in it? (optional)", multiline: true },
      ],
    });
    if (!v) return;
    try {
      const r = await mkdir.mutateAsync({ name: v.name, description: v.description });
      navigate(to.dir(r.dir));
    } catch { /* shown via mkdir.error */ }
  };

  return (
    <article>
      {dir && <Crumbs dir={parentDir(dir)} />}
      <Title>{dir ? dir.split("/").pop() : scope.index}</Title>
      {!dir && <p className="-mt-1 mb-1"><Pill>front page</Pill></p>}
      <p className="text-ink/70">{data.description ?? "No authored description."}</p>
      {(describe.error ?? mkdir.error) && <ErrorNote error={describe.error ?? mkdir.error} />}
      {!readOnly && (
        <div className="my-3 flex gap-4">
          <Btn tone="green" onClick={() => navigate(to.new(dir))}>New concept</Btn>
          <Btn tone="blue" tilt={1.2} onClick={newFolder}>New folder</Btn>
          {dir !== "" && <Btn tone="pink" tilt={-0.6} onClick={editDescription}>Edit description</Btn>}
        </div>
      )}
      {data.directories.length + data.concepts.length === 0 && (
        <div className="my-8 flex flex-wrap items-center gap-6">
          <Okie pose="shrug" size={170} />
          <p className="max-w-sm font-head text-lg text-ink/70">Nothing here yet. Tell me something and I’ll remember it.</p>
        </div>
      )}
      {data.directories.length > 0 && (
        <section aria-label="Directories">
          <h2>Directories</h2>
          <ul className="doodle-list">
            {data.directories.map((d) => (
              <li key={d.dir}>
                <Link href={to.dir(d.dir)}>{d.name}</Link>
                {d.description && <span className="text-ink/60"> — {d.description}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {data.concepts.length > 0 && (
        <section aria-label="Concepts">
          <h2>Concepts</h2>
          <ul className="doodle-list">
            {data.concepts.map((c) => (
              <li key={c.id}>
                <Link href={to.concept(c.id)}>{c.title ?? c.id}</Link> {c.type && <Pill>{c.type}</Pill>}
                {c.description && <span className="text-ink/60"> — {c.description}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
