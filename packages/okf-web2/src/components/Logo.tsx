import { Link } from "wouter";
import { Mark } from "../doodle/Mark";
import { markUrl, OkieSketch } from "../doodle/Okie";
import { crayon } from "../doodle/Sketch";

/** "OK, Fine Memory" with Okie the snail, linking to the workspace list. */
export function Logo() {
  return (
    <Link href="~/" title="OK, fine, I’ll remember it for you." className="no-wavy inline-flex shrink-0 -rotate-2 items-center gap-2 font-head text-2xl font-bold whitespace-nowrap text-ink">
      {markUrl ? <img src={markUrl} alt="" aria-hidden="true" className="-my-7 h-20 w-24 object-contain" /> : <OkieSketch size={100} className="-my-7 -ml-2" />}
      <Mark type="underline" color={crayon.red} strokeWidth={2.5} padding={1}>OK, Fine Memory</Mark>
    </Link>
  );
}
