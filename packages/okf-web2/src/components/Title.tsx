import { ReactNode } from "react";
import { Mark } from "../doodle/Mark";
import { crayon } from "../doodle/Sketch";
import { useAccent } from "../lib/accent";

/** Page heading, underlined twice in the workspace accent crayon (yellow outside one). */
export function Title({ children }: { children: ReactNode }) {
  return (
    <h1 className="mb-4 inline-block -rotate-1 font-head text-3xl leading-tight font-bold md:text-4xl">
      <Mark type="underline" color={crayon[useAccent()]} strokeWidth={4} iterations={2} padding={2}>{children}</Mark>
    </h1>
  );
}

export function Pill({ children }: { children: ReactNode }) {
  return <span className="pill">{children}</span>;
}
