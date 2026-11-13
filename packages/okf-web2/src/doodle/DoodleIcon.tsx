import { ReactNode } from "react";

/** Generated icons (ASSETS_PROMPT.md §1), used automatically once present. */
const icons = import.meta.glob<string>("../assets/doodles/icons/*.png", { eager: true, query: "?url", import: "default" });

export type IconName =
  | "folder-closed" | "folder-open" | "page" | "notebook" | "search" | "pencil" | "move" | "eraser" | "refresh"
  | "plus" | "chevron" | "collapse" | "close" | "link" | "tag" | "palette" | "warning" | "check";

/** A doodle icon: the generated PNG if it exists, else `fallback` (an inline sketch). */
export function DoodleIcon({ name, size = 24, fallback, className = "" }: { name: IconName; size?: number; fallback: ReactNode; className?: string }) {
  const src = icons[`../assets/doodles/icons/${name}.png`];
  if (!src) return <>{fallback}</>;
  return <img src={src} alt="" aria-hidden="true" width={size} height={size} className={`shrink-0 ${className}`} />;
}
