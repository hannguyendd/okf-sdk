import { CSSProperties } from "react";
import { Sketch } from "./Sketch";

/** A grey pencil scribble standing in for a line of text while it loads. */
export function Scribble({ w = "60%", h = 18, className = "", style }: { w?: string | number; h?: number; className?: string; style?: CSSProperties }) {
  return (
    <Sketch
      aria-hidden="true"
      className={`skeleton block text-ink/20 ${className}`}
      style={{ width: w, height: h, ...style }}
      pad={1}
      rough={{ stroke: "none", fill: "currentColor", fillStyle: "zigzag", fillWeight: 2, hachureGap: 4, hachureAngle: -35, roughness: 2.4 }}
    />
  );
}

/** Placeholder for a page in the main sheet: title, meta rows, a note block. */
export function PageSkeleton() {
  return (
    <div role="status" aria-label="Loading" className="flex flex-col gap-3">
      <Scribble w="55%" h={34} className="mb-3 -rotate-1" />
      <Scribble w={180} h={16} />
      <div className="my-2 flex gap-4">
        <Scribble w={70} h={30} className="-rotate-2" />
        <Scribble w={80} h={30} className="rotate-1" />
      </div>
      {[42, 68, 35].map((w, i) => (
        <div key={i} className="flex gap-6">
          <Scribble w={90} h={14} />
          <Scribble w={`${w}%`} h={14} />
        </div>
      ))}
      <Sketch aria-hidden="true" className="mt-4 flex -rotate-[0.4deg] flex-col gap-3 bg-note/60 px-6 py-5 text-ink/20" rough={{ stroke: "currentColor", strokeWidth: 1.6 }}>
        <Scribble w="40%" h={22} />
        <Scribble w="85%" h={14} />
        <Scribble w="75%" h={14} />
        <Scribble w="60%" h={14} />
      </Sketch>
    </div>
  );
}

/** Placeholder rows for the explorer notebook. */
export function TreeSkeleton({ rows = 5 }: { rows?: number }) {
  const widths = ["70%", "55%", "62%", "48%", "66%", "52%"];
  return (
    <div role="status" aria-label="Loading tree" className="flex flex-col gap-3.5 py-1.5 pl-1">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-2" style={{ paddingLeft: i % 3 === 2 ? 24 : 0 }}>
          <Scribble w={22} h={18} />
          <Scribble w={widths[i % widths.length]} h={13} />
        </div>
      ))}
    </div>
  );
}

/** Placeholder sheets for the workspace list. */
export function CardsSkeleton() {
  return (
    <div role="status" aria-label="Loading workspaces" className="mt-6 grid gap-8 sm:grid-cols-2">
      {[-1.2, 0.8].map((r) => (
        <Sketch key={r} aria-hidden="true" className="flex flex-col gap-3 bg-paper px-6 py-5 text-ink/20" style={{ rotate: `${r}deg` }} rough={{ stroke: "currentColor", strokeWidth: 2 }}>
          <Scribble w="40%" h={24} />
          <Scribble w="80%" h={14} />
          <Scribble w="65%" h={14} />
        </Sketch>
      ))}
    </div>
  );
}
