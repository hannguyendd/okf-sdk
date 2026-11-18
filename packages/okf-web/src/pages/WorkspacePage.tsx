import { Link } from "wouter";
import { Pill } from "../components/Title";
import { ErrorNote } from "../doodle/Loading";
import { Scribble } from "../doodle/Skeleton";
import { Sketch } from "../doodle/Sketch";
import { useOverview } from "../lib/queries";
import { parentDir, to } from "../lib/scope";
import { ago } from "../lib/time";
import { DirPage } from "./DirPage";

/** A workspace's front page: its root folder plus counts and what was remembered lately. */
export function WorkspacePage() {
  return <DirPage dir=""><WorkspaceOverview /></DirPage>;
}

function WorkspaceOverview() {
  const { data, error } = useOverview();
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Scribble w={260} h={14} className="my-2" />;
  const types = Object.entries(data.types).slice(0, 4);
  return (
    <>
      <p className="flex flex-wrap items-center gap-2.5 font-head text-sm">
        <span>
          {data.concepts} concept{data.concepts === 1 ? "" : "s"} remembered · {data.directories} folder{data.directories === 1 ? "" : "s"}
        </span>
        {types.map(([t, n]) => <Pill key={t} count={n}>{t}</Pill>)}
      </p>
      {data.recent.length > 0 && (
        <section aria-label="Recently remembered" className="my-4">
          <h2>Recently remembered</h2>
          <Sketch className="mt-2 rotate-[-0.3deg] bg-note px-6 py-3" rough={{ strokeWidth: 1.8 }}>
            <ul className="doodle-list">
              {data.recent.map((r) => (
                <li key={r.id}>
                  <Link href={to.concept(r.id)}>{r.title ?? r.id}</Link>{" "}
                  {r.type && <Pill>{r.type}</Pill>}{" "}
                  <span className="text-sm text-ink/55">in {parentDir(r.id) || "front page"} · {ago(r.timestamp)}</span>
                </li>
              ))}
            </ul>
          </Sketch>
        </section>
      )}
    </>
  );
}
