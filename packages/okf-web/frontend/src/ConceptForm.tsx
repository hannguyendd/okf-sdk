import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";
import { go, href } from "./route";

type Props = { mode: "new"; dir: string; onChanged: () => void } | { mode: "edit"; id: string; onChanged: () => void };

export default function ConceptForm(props: Props) {
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [body, setBody] = useState("");
  const [extra, setExtra] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(props.mode === "new");

  useEffect(() => {
    if (props.mode !== "edit") return;
    api.get(props.id).then((c) => {
      const { type, title, description, tags, timestamp: _ts, ...rest } = c.frontmatter as Record<string, any>;
      setType(type ?? ""); setTitle(title ?? ""); setDescription(description ?? "");
      setTags(Array.isArray(tags) ? tags.join(", ") : ""); setExtra(rest); setBody(c.body);
      setReady(true);
    }, (e) => setError(e.message));
  }, [props.mode === "edit" ? props.id : ""]);

  if (!ready) return error ? <p role="alert" className="text-red-700 dark:text-red-400">{error}</p> : <p>Loading…</p>;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const fm: Record<string, unknown> = { ...extra, type };
    if (title) fm.title = title;
    if (description) fm.description = description;
    const tagList = tags.split(",").map((t) => t.trim()).filter(Boolean);
    if (tagList.length) fm.tags = tagList;
    try {
      if (props.mode === "new") {
        const id = props.dir ? `${props.dir}/${name}` : name;
        await api.add(id, fm, body);
        props.onChanged(); go(href.concept(id));
      } else {
        await api.patch(props.id, fm, body);
        props.onChanged(); go(href.concept(props.id));
      }
    } catch (err) { setError((err as Error).message); }
  };

  const cancel = () => go(props.mode === "new" ? href.dir(props.dir) : href.concept(props.id));

  return (
    <form onSubmit={submit} className="flex flex-col gap-2.5 [&_label]:flex [&_label]:flex-col [&_label]:gap-1 [&_label]:text-[13px] [&_label]:text-stone-500">
      <h1>{props.mode === "new" ? `New concept in ${props.dir || "(root)"}` : `Edit ${props.id}`}</h1>
      {error && <p role="alert" className="text-red-700 dark:text-red-400">{error}</p>}
      {props.mode === "new" && (
        <label>Name<input value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. orders" /></label>
      )}
      <label>Type<input value={type} onChange={(e) => setType(e.target.value)} required /></label>
      <label>Title<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      <label>Description<input value={description} onChange={(e) => setDescription(e.target.value)} /></label>
      <label>Tags (comma separated)<input value={tags} onChange={(e) => setTags(e.target.value)} /></label>
      <label>Body<textarea rows={14} value={body} onChange={(e) => setBody(e.target.value)} /></label>
      <p className="flex gap-2">
        <button type="submit">{props.mode === "new" ? "Create" : "Save"}</button>
        <button type="button" onClick={cancel}>Cancel</button>
      </p>
    </form>
  );
}
