import { useId } from "react";
import { crayon, ink } from "./Sketch";

/**
 * Generated art (see ASSETS_PROMPT.md) is picked up automatically once the
 * files exist: Vite resolves these globs at build time and re-runs them in dev
 * when files are added. Until then the components fall back to inline sketches.
 */
const okiePoses = import.meta.glob<string>("../assets/doodles/okie/*.png", { eager: true, query: "?url", import: "default" });
const brandMark = import.meta.glob<string>("../../brand/logo/mark.png", { eager: true, query: "?url", import: "default" });

export type Pose = "sigh" | "writing" | "reading" | "asleep" | "shrug" | "oops" | "wave" | "lost-page" | "loading";

/** The brand's main logo image, if it has been generated. */
export const markUrl: string | undefined = Object.values(brandMark)[0];

/** Okie the snail in a pose; decorative (alt=""), so pair it with text. */
export function Okie({ pose = "sigh", size = 160, className = "" }: { pose?: Pose; size?: number; className?: string }) {
  const src = okiePoses[`../assets/doodles/okie/okie-${pose}.png`];
  if (src) return <img src={src} alt="" aria-hidden="true" loading="lazy" decoding="async" width={size} height={size * 0.75} className={`shrink-0 object-contain ${className}`} />;
  return <OkieSketch size={size} asleep={pose === "asleep"} className={className} />;
}

/** Placeholder Okie (same drawing as brand/brand-board.html) until the generated poses land. */
export function OkieSketch({ size = 160, asleep = false, className = "" }: { size?: number; asleep?: boolean; className?: string }) {
  const clip = `okie-shell-${useId().replace(/:/g, "")}`;
  return (
    <svg aria-hidden="true" viewBox="0 0 130 100" width={size} height={size * 0.77} className={`shrink-0 ${className}`} fill="none" strokeLinecap="round" strokeLinejoin="round">
      <defs><clipPath id={clip}><circle cx="52" cy="50" r="31" /></clipPath></defs>
      <path d="M8 84c20 5 66 6 92 1 10-2 15-11 13-21-1-8-7-12-13-11-5 1-8 6-8 11" fill="#fffef9" stroke={ink} strokeWidth="3" />
      <path d="M18 86c22 3 56 3 76-1" stroke={crayon.pink} strokeWidth="3" strokeDasharray="7 5" />
      <path d="M100 56c-2-8-6-15-9-22M108 58c1-9 3-17 6-24" stroke={ink} strokeWidth="3" />
      <circle cx="90" cy="29" r="6.5" fill="#fff" stroke={ink} strokeWidth="2.6" />
      <circle cx="115" cy="29" r="6.5" fill="#fff" stroke={ink} strokeWidth="2.6" />
      {asleep
        ? <path d="M84 30c3 3 9 3 12 0M109 30c3 3 9 3 12 0" stroke={ink} strokeWidth="2.4" />
        : <>
            <path d="M83.5 29a6.5 6.5 0 0 1 13 0zM108.5 29a6.5 6.5 0 0 1 13 0z" fill="#ffd9e3" stroke={ink} strokeWidth="2.2" />
            <circle cx="90" cy="32" r="2" fill={ink} /><circle cx="115" cy="32" r="2" fill={ink} />
          </>}
      <path d="M104 72h7" stroke={ink} strokeWidth="2.6" />
      {asleep
        ? <path d="M118 52h8l-8 8h8M122 40h6l-6 6h6" stroke={ink} strokeWidth="2" opacity=".7" />
        : <path d="M118 68c3-3 8-2 8 2s-4 5-6 3" stroke={ink} strokeWidth="2" opacity=".7" />}
      <circle cx="52" cy="50" r="31" fill="#fffef9" />
      <g clipPath={`url(#${clip})`}>
        <path d="M14 26l10 52M22 22l10 60M30 18l10 64M38 16l10 66M46 16l10 66M54 16l10 66M62 16l10 66M70 18l10 64M78 22l10 60M86 28l6 44" stroke={crayon.yellow} strokeWidth="6" />
      </g>
      <circle cx="52" cy="50" r="31" stroke={ink} strokeWidth="3" />
      <path d="M52 50c0-3 4-4 6-1 3 4-1 9-6 9-7 0-11-7-9-13 3-9 14-12 21-7 9 6 9 20 1 27-10 8-26 6-32-5" stroke={ink} strokeWidth="3" />
    </svg>
  );
}
