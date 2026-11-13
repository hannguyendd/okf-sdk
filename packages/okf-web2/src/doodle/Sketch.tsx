import { AllHTMLAttributes, ElementType, useLayoutEffect, useRef, useState } from "react";
import rough from "roughjs";
import type { Options } from "roughjs/bin/core";

/** Light-theme ink, for art that must stay dark in both themes (Okie is a sticker). Sketch outlines use currentColor. */
export const ink = "#2b3a67";
export const crayon = {
  yellow: "#ffd23f",
  pink: "#ff9fb6",
  green: "#9be564",
  blue: "#6aa8ff",
  red: "#ff7b6b",
  orange: "#ffb703",
  purple: "#b79cff",
} as const;
export type Tone = keyof typeof crayon;

/** A crayon scribble fill: loose zigzag strokes like a kid colouring in. */
export const scribble = (tone: Tone): Options => ({
  fill: crayon[tone],
  fillStyle: "zigzag",
  fillWeight: 2.4,
  hachureGap: 4.5,
  hachureAngle: -40,
});

type SketchProps = AllHTMLAttributes<HTMLElement> & {
  as?: ElementType;
  /** rough.js options for the outline (and fill). */
  rough?: Options;
  shape?: "rect" | "ellipse";
  /** Inset of the drawing from the element's edges, in px. */
  pad?: number;
};

/**
 * Renders `as` with a hand-drawn rough.js outline (and optional crayon fill)
 * behind its children, redrawn when the element resizes. The seed is fixed per
 * instance so redraws keep the same wobble.
 */
export function Sketch({ as: Tag = "div", rough: opts, shape = "rect", pad = 2, className = "", children, ...rest }: SketchProps) {
  const ref = useRef<HTMLElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [seed] = useState(() => 1 + Math.floor(Math.random() * 2 ** 30));
  const optsKey = JSON.stringify(opts ?? {});

  useLayoutEffect(() => {
    const el = ref.current;
    const svg = svgRef.current;
    if (!el || !svg) return;
    const draw = () => {
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      svg.replaceChildren();
      if (!w || !h) return;
      const rc = rough.svg(svg);
      const o: Options = { stroke: "currentColor", strokeWidth: 2, roughness: 1.9, bowing: 1.6, seed, ...opts };
      svg.appendChild(
        shape === "ellipse"
          ? rc.ellipse(w / 2, h / 2, w - pad * 2, h - pad * 2, o)
          : rc.rectangle(pad, pad, w - pad * 2, h - pad * 2, o),
      );
    };
    draw();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(draw);
    ro.observe(el);
    return () => ro.disconnect();
  }, [optsKey, seed, shape, pad]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Tag ref={ref} className={`relative isolate ${className}`} {...rest}>
      <svg ref={svgRef} aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 size-full overflow-visible" />
      {children}
    </Tag>
  );
}
