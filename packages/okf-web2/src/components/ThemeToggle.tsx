import { useEffect, useState } from "react";
import { Sketch } from "../doodle/Sketch";

const KEY = "okf-theme";
type Theme = "light" | "dark";

const systemTheme = (): Theme => (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
const stored = (): Theme | null => {
  try { const t = localStorage.getItem(KEY); return t === "light" || t === "dark" ? t : null; } catch { return null; }
};
const apply = (t: Theme) => document.documentElement.classList.toggle("dark", t === "dark");

/**
 * Notebook (light) ↔ chalkboard (dark). Follows the OS until the user picks one;
 * the choice is remembered. index.html applies it before first paint.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? systemTheme());

  useEffect(() => { apply(theme); }, [theme]);
  useEffect(() => {
    if (stored()) return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => { if (!stored()) setTheme(mq.matches ? "dark" : "light"); };
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  const next: Theme = theme === "dark" ? "light" : "dark";
  const flip = () => {
    try { localStorage.setItem(KEY, next); } catch { /* storage unavailable */ }
    setTheme(next);
  };
  return (
    <Sketch as="button" type="button" shape="ellipse" onClick={flip} pad={1}
      aria-label={next === "dark" ? "Switch to chalkboard (dark) mode" : "Switch to notebook (light) mode"}
      title={next === "dark" ? "Chalkboard mode" : "Notebook mode"}
      className="doodle-btn grid size-10 shrink-0 place-items-center text-xl leading-none"
      rough={{ strokeWidth: 2, roughness: 1.6 }}>
      <span aria-hidden="true">{theme === "dark" ? "☀︎" : "☾"}</span>
    </Sketch>
  );
}
