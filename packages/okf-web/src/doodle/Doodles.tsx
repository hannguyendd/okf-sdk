import { useEffect, useRef } from "react";
import rough from "roughjs";
import { crayon, ink } from "./Sketch";

/** Kid drawings in the page margins: sun, cloud, house, flower, stars. Static, drawn once. */
export function Doodles() {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    const rc = rough.svg(svg);
    const pen = { stroke: "currentColor", strokeWidth: 2.2, roughness: 2.2, bowing: 2, seed: 7 };
    const add = (...nodes: SVGGElement[]) => nodes.forEach((n) => svg.appendChild(n));
    const color = (c: string, extra = {}) => ({ ...pen, fill: c, fillStyle: "zigzag", fillWeight: 2, hachureGap: 5, ...extra });

    // sun (top right)
    add(rc.circle(1180, 90, 80, color(crayon.yellow, { stroke: crayon.orange })));
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2;
      add(rc.line(1180 + Math.cos(a) * 52, 90 + Math.sin(a) * 52, 1180 + Math.cos(a) * 78, 90 + Math.sin(a) * 78, { ...pen, stroke: crayon.orange }));
    }
    add(rc.arc(1180, 96, 34, 22, 0.2, Math.PI - 0.2, false, pen), rc.circle(1167, 82, 5, color(ink)), rc.circle(1193, 82, 5, color(ink)));
    // cloud
    add(rc.path("M1010 190c-22 0-24-28-4-31 0-20 27-26 38-11 7-22 43-22 49 0 15-10 36 0 31 18 21 0 22 26 1 26z", color("#ffffff")));
    // house (bottom right)
    add(
      rc.rectangle(1100, 650, 120, 95, color(crayon.pink)),
      rc.polygon([[1088, 652], [1160, 590], [1232, 652]], color(crayon.red)),
      rc.rectangle(1145, 690, 32, 55, color(crayon.blue)),
      rc.rectangle(1112, 668, 24, 22, color(crayon.yellow)),
    );
    // flower (bottom left)
    add(rc.line(70, 760, 74, 660, { ...pen, stroke: "#3f9b3a" }), rc.ellipse(92, 720, 36, 16, color(crayon.green)));
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2;
      add(rc.circle(74 + Math.cos(a) * 18, 645 + Math.sin(a) * 18, 22, color(crayon.purple)));
    }
    add(rc.circle(74, 645, 16, color(crayon.yellow)));
    // stars
    const star = (x: number, y: number, r: number, c: string) =>
      rc.polygon(Array.from({ length: 10 }, (_, i) => {
        const a = -Math.PI / 2 + (i * Math.PI) / 5;
        const rr = i % 2 ? r * 0.45 : r;
        return [x + Math.cos(a) * rr, y + Math.sin(a) * rr] as [number, number];
      }), color(c));
    add(star(60, 470, 20, crayon.yellow), star(1240, 420, 14, crayon.pink), star(1050, 520, 11, crayon.blue));
  }, []);

  return (
    <svg
      ref={ref}
      aria-hidden="true"
      viewBox="0 0 1280 800"
      preserveAspectRatio="xMidYMid slice"
      className="pointer-events-none fixed inset-0 -z-10 hidden size-full text-ink opacity-90 lg:block"
    />
  );
}
