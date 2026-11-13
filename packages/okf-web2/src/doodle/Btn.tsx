import { ButtonHTMLAttributes } from "react";
import { scribble, Sketch, Tone } from "./Sketch";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { tone?: Tone; tilt?: number; small?: boolean };

/** A crayon-coloured button with a wobbly double outline. */
export function Btn({ tone = "yellow", tilt = -1.5, small, className = "", style, type = "button", ...props }: Props) {
  return (
    <Sketch
      as="button"
      type={type}
      rough={{ ...scribble(tone), roughness: 2.1 }}
      pad={1}
      style={{ rotate: `${tilt}deg`, ...style }}
      className={`doodle-btn ${small ? "px-3 text-sm leading-6" : "px-4 leading-8"} ${className}`}
      {...props}
    />
  );
}
