import { Link } from "wouter";
import { Pill, Title } from "../components/Title";
import { ErrorNote, Loading } from "../doodle/Loading";
import { Okie } from "../doodle/Okie";
import { Sketch } from "../doodle/Sketch";
import { useInfo, useSearch } from "../lib/queries";
import { to } from "../lib/scope";

export function SearchPage({ q }: { q: string }) {
  const enabled = useInfo().data?.search_enabled;
  const { data: hits, error } = useSearch(q, enabled === true);

  return (
    <article>
      <Title>Search: {q}</Title>
      <p className="text-ink/70">Semantic match over directory listings (<code>_index.md</code>) and the index description.</p>
      {enabled === false ? (
        <div className="my-6 flex flex-wrap items-center gap-6">
          <Okie pose="asleep" size={180} />
          <p className="max-w-md font-head text-lg">Search is napping. Set <code>OKF_EMBEDDING_URL</code> and <code>OKF_EMBEDDING_MODEL</code> to wake it up.</p>
        </div>
      ) : error ? <ErrorNote error={error} /> : !hits ? <Loading label="Searching…" /> : hits.length === 0 ? (
        <div className="my-6 flex flex-wrap items-center gap-6">
          <Okie pose="shrug" size={180} />
          <p className="font-head text-lg">I looked. Nothing. Try other words?</p>
        </div>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-4 p-0">
          {hits.map((h) => (
            <li key={`${h.bundle}:${h.path ?? ""}`}>
              {h.kind === "bundle"
                ? <Link href={to.dir("")}><Pill>index</Pill> {h.bundle}</Link>
                : <Link href={to.dir(h.dir)}>{h.dir || "front page"}</Link>}{" "}
              <Pill>{h.score.toFixed(2)}</Pill>
              <Sketch className="mt-1 rotate-[-0.4deg] bg-note px-4 py-2" rough={{ strokeWidth: 1.6 }}>
                <pre className="m-0 font-hand text-base whitespace-pre-wrap">{h.excerpt}</pre>
              </Sketch>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
