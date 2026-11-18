import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { MotionGlobalConfig } from "motion/react";
import { setupServer } from "msw/node";
import { toast } from "sonner";
import { afterAll, afterEach, beforeAll } from "vitest";

// happy-dom's Web Animations reject when motion cancels them; tests only care about end states
MotionGlobalConfig.skipAnimations = true;

/** One MSW server for the run; each test installs its own fake backend with `server.use`. */
export const server = setupServer();

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  cleanup();
  // sonner replays still-active toasts to the next mounted <Toaster>
  toast.dismiss();
  server.resetHandlers();
  localStorage.clear();
  window.location.hash = "";
});
afterAll(() => server.close());
