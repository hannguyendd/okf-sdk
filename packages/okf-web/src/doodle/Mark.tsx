import { ReactNode, useEffect, useRef } from "react";
import { annotate } from "rough-notation";
import type { RoughAnnotationType } from "rough-notation/lib/model";
import { crayon } from "./Sketch";

interface Props {
  children: ReactNode;
  type?: RoughAnnotationType;
  color?: string;
  show?: boolean;
  strokeWidth?: number;
  padding?: number;
  iterations?: number;
  className?: string;
}

/**
 * Marker-pen annotation (underline, highlight, circle…) drawn by rough-notation.
 * rough-notation positions its SVG once, against the nearest positioned
 * ancestor; the relative wrapper makes that ancestor move with the text, so
 * the mark stays put when content above it shifts (e.g. a tree branch loads).
 */
export function Mark({ children, type = "highlight", color = crayon.yellow, show = true, strokeWidth, padding, iterations, className }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!show || !el || !el.offsetWidth) return; // nothing to draw on (hidden, or a test DOM)
    const a = annotate(el, { type, color, strokeWidth, padding, iterations, multiline: true, animationDuration: 450 });
    a.show();
    return () => a.remove();
  }, [show, type, color, strokeWidth, padding, iterations]);
  return (
    <span className={`relative inline-block ${className ?? ""}`}>
      <span ref={ref}>{children}</span>
    </span>
  );
}
