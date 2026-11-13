import { Fragment } from "react";
import { Link } from "wouter";
import { to, useScope } from "../lib/scope";

/**
 * "notebook › folder › folder" trail above a page. Every step links to that
 * directory (the first one to the index root), so you can always climb back
 * up to add things there. `dir` is the directory the page lives in.
 */
export function Crumbs({ dir, current }: { dir: string; current?: string }) {
  const { index } = useScope();
  const parts = dir ? dir.split("/") : [];
  return (
    <nav aria-label="Breadcrumb" className="mb-1 flex flex-wrap items-center gap-x-1.5 font-head text-sm text-ink/60">
      <Link href={to.dir("")} className="no-wavy hover:underline">📒 {index}</Link>
      {parts.map((p, i) => (
        <Fragment key={i}>
          <span aria-hidden="true">›</span>
          <Link href={to.dir(parts.slice(0, i + 1).join("/"))} className="no-wavy hover:underline">{p}</Link>
        </Fragment>
      ))}
      {current && (
        <>
          <span aria-hidden="true">›</span>
          <span aria-current="page" className="text-ink/80">{current}</span>
        </>
      )}
    </nav>
  );
}
