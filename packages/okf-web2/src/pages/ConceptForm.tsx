import { useForm } from "react-hook-form";
import { useLocation } from "wouter";
import { Crumbs } from "../components/Crumbs";
import { Title } from "../components/Title";
import { Btn } from "../doodle/Btn";
import { ErrorNote } from "../doodle/Loading";
import { PageSkeleton } from "../doodle/Skeleton";
import { api, Concept } from "../lib/api";
import { useConcept, useIndexMutation, useOverview } from "../lib/queries";
import { parentDir, to, useScope } from "../lib/scope";

type Props = { mode: "new"; dir: string } | { mode: "edit"; id: string };

interface Fields { name: string; type: string; title: string; description: string; tags: string; body: string }

const KNOWN = ["type", "title", "description", "tags", "timestamp"];

function toFields(c?: Concept): Fields {
  const fm = (c?.frontmatter ?? {}) as Record<string, unknown>;
  const s = (v: unknown) => (typeof v === "string" ? v : "");
  return {
    name: "",
    type: s(fm.type),
    title: s(fm.title),
    description: s(fm.description),
    tags: Array.isArray(fm.tags) ? fm.tags.join(", ") : "",
    body: c?.body ?? "",
  };
}

export function ConceptForm(props: Props) {
  if (props.mode === "new") return <Form {...props} />;
  return <EditLoader id={props.id} />;
}

function EditLoader({ id }: { id: string }) {
  const { data, error } = useConcept(id);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <PageSkeleton />;
  return <Form mode="edit" id={id} concept={data} />;
}

function Form(props: Props & { concept?: Concept }) {
  const [, navigate] = useLocation();
  const types = Object.keys(useOverview(useScope()).data?.types ?? {});
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({ defaultValues: toFields(props.concept) });
  const save = useIndexMutation(async (s, f: Fields) => {
    // keep producer-defined keys the form doesn't show; the server manages `timestamp`
    const extra = Object.fromEntries(Object.entries(props.concept?.frontmatter ?? {}).filter(([k]) => !KNOWN.includes(k)));
    const fm: Record<string, unknown> = { ...extra, type: f.type };
    if (f.title) fm.title = f.title;
    if (f.description) fm.description = f.description;
    const tags = f.tags.split(",").map((t) => t.trim()).filter(Boolean);
    if (tags.length) fm.tags = tags;
    if (props.mode === "new") {
      const id = props.dir ? `${props.dir}/${f.name}` : f.name;
      await api.add(s, id, fm, f.body);
      return id;
    }
    await api.patch(s, props.id, fm, f.body);
    return props.id;
  }, () => (props.mode === "new" ? "Fine, I’ll keep this one too." : "Fine. Remembered."));

  const submit = handleSubmit(async (f) => {
    try { navigate(to.concept(await save.mutateAsync(f))); } catch { /* shown via save.error */ }
  });
  const cancel = () => navigate(props.mode === "new" ? to.dir(props.dir) : to.concept(props.id));

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Crumbs dir={props.mode === "new" ? props.dir : parentDir(props.id)} current={props.mode === "new" ? "new concept" : "editing"} />
      <Title>{props.mode === "new" ? props.dir ? `New concept in ${props.dir}` : "New concept on the front page" : `Edit ${props.id}`}</Title>
      {save.error && <ErrorNote error={save.error} />}
      {props.mode === "new" && (
        <label className="field">Name<input className="field-line" placeholder="e.g. orders" {...register("name", { required: true })} /></label>
      )}
      <label className="field">Type<input className="field-line" list="okf-types" placeholder="e.g. Playbook" {...register("type", { required: true })} /></label>
      <datalist id="okf-types">{types.map((t) => <option key={t} value={t} />)}</datalist>
      {errors.type && <p className="text-sm text-red-600">Type is required.</p>}
      <label className="field">Title<input className="field-line" {...register("title")} /></label>
      <label className="field">Description<input className="field-line" {...register("description")} /></label>
      <label className="field">Tags (comma separated)<input className="field-line" {...register("tags")} /></label>
      <label className="field">Body<textarea className="field-box" rows={14} {...register("body")} /></label>
      <div className="mt-2 flex gap-4">
        <Btn tone="green" type="submit" disabled={isSubmitting}>{props.mode === "new" ? "Create" : "Save"}</Btn>
        <Btn tone="blue" tilt={1.2} onClick={cancel}>Cancel</Btn>
      </div>
    </form>
  );
}
