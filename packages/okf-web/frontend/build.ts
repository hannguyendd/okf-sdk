import tailwind from "bun-plugin-tailwind";
import { rmSync } from "node:fs";

rmSync("../src/okf_web/static", { recursive: true, force: true });

const result = await Bun.build({
  entrypoints: ["./index.html"],
  outdir: "../src/okf_web/static",
  minify: true,
  publicPath: "/",
  plugins: [tailwind],
});
if (!result.success) {
  for (const log of result.logs) console.error(log);
  process.exit(1);
}
console.log(`built ${result.outputs.length} files`);
