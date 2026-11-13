import { createContext, CSSProperties, ReactNode, useContext } from "react";
import { crayon, Tone } from "../doodle/Sketch";
import type { WorkspaceInfo } from "./api";

export const TONES = Object.keys(crayon) as Tone[];

/** The workspace's chosen colour, or a stable pick from its name so workspaces differ by default. */
export function toneOf(ws: Pick<WorkspaceInfo, "name" | "color"> | undefined): Tone {
  if (ws?.color) return ws.color;
  if (!ws) return "blue";
  let h = 0;
  for (const ch of ws.name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TONES[h % TONES.length];
}

const AccentContext = createContext<Tone | null>(null);

/** Colours everything inside it (cover, highlights, underlines, tape) with `tone`. */
export function AccentProvider({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <AccentContext.Provider value={tone}>
      <div className={className} style={{ "--accent": crayon[tone] } as CSSProperties}>{children}</div>
    </AccentContext.Provider>
  );
}

/** Current accent tone; yellow outside a workspace. */
export const useAccent = (): Tone => useContext(AccentContext) ?? "yellow";
