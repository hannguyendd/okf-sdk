import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useLocation } from "wouter";
import { Crumbs } from "../components/Crumbs";
import { useDialogs } from "../components/Dialogs";
import { Pill, Title } from "../components/Title";
import { Btn } from "../doodle/Btn";
import { ErrorNote } from "../doodle/Loading";
import { PageSkeleton } from "../doodle/Skeleton";
import { Sketch } from "../doodle/Sketch";
import { api } from "../lib/api";
import { useConcept, useDirs, useIndexMutation, useReadOnly } from "../lib/queries";
import { parentDir, to } from "../lib/scope";

/** Rewrite a relative `.md` link in a concept body to an in-app route. */
function resolveLink(id: string, target: string): string | null {
  if (/^[a-z]+:/i.test(target) || !target.endsWith(".md")) return null;
  const parts = id.split("/").slice(0, -1);
  for (const seg of target.replace(/\.md$/, "").split("/")) {
    if (seg === "..") parts.pop();
    else if (seg !== "." && seg !== "") parts.push(seg);
  }
  return to.concept(parts.join("/"));
}

const show = (v: unknown) =>
  Array.isArray(v) ? v.map((t) => <Pill key={String(t)}>{String(t)}</Pill>) : typeof v === "string" ? v : JSON.stringify(v);

export function ConceptPage({ id }: { id: string }) {
  const { data: concept, error } = useConcept(id);
  const readOnly = useReadOnly();
  const dirs = useDirs(!readOnly);
  const dialogs = useDialogs();
  const [, navigate] = useLocation();
  const move = useIndexMutation((s, dest: string) => api.move(s, id, dest), () => "Moved it. Links are fixed, you’re welcome.");
  const remove = useIndexMutation(
    (s, force: boolean) => api.remove(s, id, force),
    (r) => (r.action === "blocked" ? null : "Erased. I’ll pretend I never knew."),
  );

  if (error) return <ErrorNote error={error} />;
  if (!concept) return <PageSkeleton />;
  const { title, ...rest } = concept.frontmatter;

  const onMove = async () => {
    const v = await dialogs.form({
      title: "Move or rename",
      submitLabel: "Move",
      fields: [
        {
          name: "folder", label: "Folder", initial: parentDir(id),
          options: [{ value: "", label: `📒 ${"(front of the notebook)"}` }, ...(dirs.data?.dirs ?? []).map((d) => ({ value: d, label: d }))],
        },
        { name: "name", label: "Name", initial: id.split("/").pop(), required: true, hint: "Letters, numbers, - _ ." },
      ],
    });
    if (!v) return;
    const dest = v.folder ? `${v.folder}/${v.name.trim()}` : v.name.trim();
    if (dest === id) return;
    try { await move.mutateAsync(dest); } catch { return; } // shown via move.error
    navigate(to.concept(dest));
  };
  const onDelete = () => deleteFlow().catch(() => {}); // failures are shown via remove.error
  const deleteFlow = async () => {
    if (!(await dialogs.confirm({ title: "Erase this concept?", message: <p>Erase <code>{id}</code>? I won’t be able to un-know it.</p>, confirmLabel: "Erase", danger: true }))) return;
    const r = await remove.mutateAsync(false);
    if (r.action === "blocked") {
      const force = await dialogs.confirm({
        title: "Other pages link here",
        message: (
          <>
            <p>Referenced by:</p>
            <ul className="doodle-list">{(r.referenced_by ?? []).map((ref) => <li key={ref}><code>{ref}</code></li>)}</ul>
            <p>Erase anyway and unlink them?</p>
          </>
        ),
        confirmLabel: "Erase anyway",
        danger: true,
      });
      if (!force) return;
      await remove.mutateAsync(true);
    }
    navigate(to.dir(parentDir(id)));
  };

  const failed = move.error ?? remove.error;
  return (
    <article>
      <Crumbs dir={parentDir(id)} />
      <Title>{String(title ?? id)}</Title>
      <p><code className="rounded bg-chip px-2 py-0.5 text-sm">{id}</code></p>
      {!readOnly && (
        <div className="my-3 flex gap-4">
          <Btn onClick={() => navigate(to.edit(id))}>Edit</Btn>
          <Btn tone="pink" tilt={1.3} onClick={onMove} title="Move to another folder or rename">Move</Btn>
          <Btn tone="red" tilt={-0.5} onClick={onDelete}>Delete</Btn>
        </div>
      )}
      {failed && <ErrorNote error={failed} />}
      <table className="my-3">
        <tbody>
          {Object.entries(rest).map(([k, v]) => (
            <tr key={k}>
              <th className="pr-5 text-left align-top font-head font-normal text-ink/55">{k}</th>
              <td>{show(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Sketch className="markdown my-4 rotate-[-0.4deg] bg-note px-6 py-4" rough={{ strokeWidth: 1.8 }}>
        <Markdown remarkPlugins={[remarkGfm]} components={{ a: ({ href, children }) => {
          const internal = resolveLink(id, href ?? "");
          return internal ? <Link href={internal}>{children}</Link> : <a href={href} target="_blank" rel="noreferrer">{children}</a>;
        } }}>
          {concept.body}
        </Markdown>
      </Sketch>
      <div className="grid gap-x-10 sm:grid-cols-2">
        {concept.links_to.length > 0 && (
          <section aria-label="Links to">
            <h2>Links to</h2>
            <ul className="doodle-list">{concept.links_to.map((l) => <li key={l}><Link href={to.concept(l)}>{l}</Link></li>)}</ul>
          </section>
        )}
        {(concept.linked_from?.length ?? 0) > 0 && (
          <section aria-label="Linked from">
            <h2>Linked from</h2>
            <ul className="doodle-list">{concept.linked_from!.map((l) => <li key={l}><Link href={to.concept(l)}>{l}</Link></li>)}</ul>
          </section>
        )}
      </div>
    </article>
  );
}
