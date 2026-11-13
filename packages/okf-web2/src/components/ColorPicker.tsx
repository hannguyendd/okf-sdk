import { crayon, Sketch, Tone } from "../doodle/Sketch";
import { TONES } from "../lib/accent";
import type { WorkspaceColor } from "../lib/api";

/** A row of crayon dots; the current one is circled. */
export function ColorPicker({ name, value, chosen, onPick }: { name: string; value: Tone; chosen: boolean; onPick: (t: WorkspaceColor) => void }) {
  return (
    <div role="radiogroup" aria-label={`Colour of ${name}`} className="flex items-center gap-1.5">
      {TONES.map((t) => {
        const on = t === value;
        return (
          <button
            key={t}
            role="radio"
            aria-checked={on && chosen}
            aria-label={t}
            title={t}
            onClick={() => onPick(t)}
            className={`grid size-6 cursor-pointer place-items-center transition-transform hover:scale-125 ${on ? "scale-110" : ""}`}
          >
            <Sketch as="span" shape="ellipse" className="block size-4" pad={0}
              rough={{ fill: crayon[t], fillStyle: "solid", stroke: on ? "currentColor" : crayon[t], strokeWidth: on ? 2.2 : 1, roughness: 1.4 }} />
          </button>
        );
      })}
    </div>
  );
}
