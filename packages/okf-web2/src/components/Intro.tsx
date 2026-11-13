import { useEffect, useState } from "react";
import { Okie } from "../doodle/Okie";

const SEEN = "okf-intro-seen";
const LENGTH_MS = 3300;

/** Whether to play the intro: once per tab, never under reduced motion or in tests. */
function shouldPlay(): boolean {
  if (import.meta.env.MODE === "test") return false;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  if (new URLSearchParams(location.search).has("intro")) return true; // ?intro forces it
  try { return sessionStorage.getItem(SEEN) !== "1"; } catch { return true; }
}

/**
 * Opening scene: Okie crawls in along a pencil trail, the name writes itself,
 * the tagline types out with a sigh, then the sheet lifts away. The app renders
 * (and fetches) underneath the whole time; any click or key skips ahead.
 */
export function Intro() {
  const [phase, setPhase] = useState<"play" | "leave" | "done">(() => (shouldPlay() ? "play" : "done"));

  useEffect(() => {
    if (phase !== "play") return;
    try { sessionStorage.setItem(SEEN, "1"); } catch { /* storage unavailable */ }
    const leave = () => setPhase("leave");
    const t = setTimeout(leave, LENGTH_MS);
    addEventListener("keydown", leave, { once: true });
    return () => { clearTimeout(t); removeEventListener("keydown", leave); };
  }, [phase]);

  useEffect(() => {
    if (phase !== "leave") return;
    const t = setTimeout(() => setPhase("done"), 600);
    return () => clearTimeout(t);
  }, [phase]);

  if (phase === "done") return null;
  return (
    <div role="presentation" onClick={() => setPhase("leave")} className={`intro ${phase === "leave" ? "intro-leave" : ""}`}>
      <div className="intro-stage">
        <svg aria-hidden="true" className="intro-trail" viewBox="0 0 600 40" preserveAspectRatio="none">
          <path d="M4 26c60-10 120 8 180-2s120-12 180 0 110 8 150-6" />
          <path d="M520 22l12 10 26-24" className="intro-check" />
        </svg>
        <div className="intro-okie"><Okie pose="sigh" size={300} /></div>
        <div className="intro-sigh" aria-hidden="true">~ sigh ~</div>
      </div>
      <h1 className="intro-name">OK, Fine Memory</h1>
      <p className="intro-tagline">OK, fine, I’ll remember it for you.</p>
      <p className="intro-skip">click anywhere to skip</p>
    </div>
  );
}
