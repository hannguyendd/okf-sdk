import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { afterEach, expect } from "bun:test";

GlobalRegistrator.register({ url: "http://localhost/" });

const matchers = await import("@testing-library/jest-dom/matchers");
expect.extend(matchers as any);
const { cleanup } = await import("@testing-library/react");
afterEach(() => cleanup());
