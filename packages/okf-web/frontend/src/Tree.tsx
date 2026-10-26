import { useEffect, useState } from "react";
import { api, Tree as TreeData } from "./api";
import { href } from "./route";

function Node({ dir, name, version }: { dir: string; name: string; version: number }) {
  const [open, setOpen] = useState(dir === "");
  const [data, setData] = useState<TreeData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    api.tree(dir).then(setData, (e) => setError(e.message));
  }, [open, dir, version]);

  return (
    <li>
      {dir !== "" && (
        <div className="flex items-center gap-0.5">
          <button aria-label={`Toggle ${name}`} aria-expanded={open} className="border-0! px-1! py-0.5! text-stone-500" onClick={() => setOpen(!open)}>
            {open ? "▾" : "▸"}
          </button>
          <a href={href.dir(dir)}>{name}</a>
        </div>
      )}
      {open && error && <p className="text-red-700 dark:text-red-400">{error}</p>}
      {open && data && (
        <ul className="list-none pl-3.5">
          {data.directories.map((d) => <Node key={d.dir} dir={d.dir} name={d.name} version={version} />)}
          {data.concepts.map((c) => (
            <li key={c.id} className="pl-5"><a href={href.concept(c.id)}>{c.title ?? c.id.split("/").pop()}</a></li>
          ))}
        </ul>
      )}
    </li>
  );
}

/** Lazy directory tree; `version` bumps force every open node to refetch after a write. */
export default function Tree({ version }: { version: number }) {
  return (
    <nav aria-label="Bundle tree">
      <ul className="m-0 list-none p-0"><Node dir="" name="/" version={version} /></ul>
    </nav>
  );
}
