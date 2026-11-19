import tailwind from "bun-plugin-tailwind";
import index from "./index.html";

// Dev server with HMR; proxies /api to the Python server (okf-web on 8765).
void tailwind;
const api = process.env.OKF_API ?? "http://127.0.0.1:8765";
const port = Number(process.env.PORT ?? 3000);
Bun.serve({
  port,
  routes: { "/": index, "/*": index },
  async fetch(req) {
    const url = new URL(req.url);
    if (url.pathname.startsWith("/api")) return fetch(api + url.pathname + url.search, req);
    return new Response("not found", { status: 404 });
  },
  development: true,
});
console.log(`dev server on http://localhost:${port}`);
