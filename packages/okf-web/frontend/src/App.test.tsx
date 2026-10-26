import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "bun:test";
import App from "./App";
import { installFakeApi } from "./fakeApi";

beforeEach(() => {
  window.location.hash = "";
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

async function openConcept(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /tables/ }));
  await user.click(await within(screen.getByRole("navigation")).findByRole("link", { name: "Orders" }));
}

describe("browse and view", () => {
  it("expands a directory lazily and shows a concept", async () => {
    const api = installFakeApi();
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("/mem")).toBeInTheDocument();
    await openConcept(user);
    expect(await screen.findByRole("heading", { name: "Orders" })).toBeInTheDocument();
    expect(screen.getByText("table")).toBeInTheDocument();
    expect(api.calls.some((c) => c.url === "/api/tree?dir=tables")).toBe(true);
  });

  it("navigates outgoing links", async () => {
    installFakeApi();
    const user = userEvent.setup();
    render(<App />);
    await openConcept(user);
    const links = await screen.findByRole("region", { name: "Links to" });
    await user.click(within(links).getByRole("link", { name: "tables/users" }));
    expect(await screen.findByRole("heading", { name: "Users" })).toBeInTheDocument();
  });

  it("shows an error for a missing concept", async () => {
    installFakeApi();
    window.location.hash = "#/c/nope/x";
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("concept not found");
  });
});

describe("search", () => {
  it("shows hits and opens the directory", async () => {
    installFakeApi({ search: true });
    const user = userEvent.setup();
    render(<App />);
    await user.type(await screen.findByRole("searchbox"), "orders{Enter}");
    const hit = await within(screen.getByRole("main")).findByRole("link", { name: /tables/ });
    expect(screen.getByText(/0\.91/)).toBeInTheDocument();
    await user.click(hit);
    expect(await screen.findByRole("heading", { name: "tables" })).toBeInTheDocument();
  });

  it("surfaces a not-configured error", async () => {
    installFakeApi({ search: false });
    const user = userEvent.setup();
    render(<App />);
    await user.type(await screen.findByRole("searchbox"), "x{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("embedding is not configured");
  });
});

describe("manage", () => {
  it("edits a concept via patch", async () => {
    const api = installFakeApi();
    const user = userEvent.setup();
    render(<App />);
    await openConcept(user);
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const body = screen.getByLabelText("Body");
    await user.clear(body);
    await user.type(body, "new text");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.concepts["tables/orders"].body).toBe("new text"));
    expect(await screen.findByText("new text")).toBeInTheDocument();
  });

  it("adds a concept in a directory", async () => {
    const api = installFakeApi();
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /tables/ }));
    await user.click(await within(screen.getByRole("navigation")).findByRole("link", { name: "tables" }));
    await user.click(await screen.findByRole("button", { name: "New concept" }));
    await user.type(screen.getByLabelText("Name"), "events");
    await user.type(screen.getByLabelText("Type"), "table");
    await user.type(screen.getByLabelText("Title"), "Events");
    await user.type(screen.getByLabelText("Body"), "hello");
    await user.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(api.concepts["tables/events"]).toBeDefined());
    expect(api.concepts["tables/events"].frontmatter).toMatchObject({ type: "table", title: "Events" });
    expect(await screen.findByRole("heading", { name: "Events" })).toBeInTheDocument();
  });

  it("moves a concept", async () => {
    const api = installFakeApi();
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue("models/orders");
    render(<App />);
    await openConcept(user);
    await user.click(await screen.findByRole("button", { name: "Move" }));
    await waitFor(() => expect(api.concepts["models/orders"]).toBeDefined());
    expect(window.location.hash).toBe("#/c/models/orders");
  });

  it("offers force delete when blocked", async () => {
    const api = installFakeApi();
    const user = userEvent.setup();
    window.location.hash = "#/c/tables/users";
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("tables/orders");
    await user.click(screen.getByRole("button", { name: "Delete anyway" }));
    await waitFor(() => expect(api.concepts["tables/users"]).toBeUndefined());
  });

  it("describes a directory and reindexes", async () => {
    const api = installFakeApi();
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue("Fresh description");
    window.location.hash = "#/d/tables";
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Edit description" }));
    await waitFor(() => expect(api.calls.find((c) => c.url === "/api/describe")?.body).toEqual({ dir: "tables", description: "Fresh description" }));
    await user.click(screen.getByRole("button", { name: "Reindex" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Reindexed");
  });

  it("hides write controls when read-only", async () => {
    installFakeApi({ readOnly: true });
    const user = userEvent.setup();
    render(<App />);
    await openConcept(user);
    await screen.findByRole("heading", { name: "Orders" });
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reindex" })).toBeNull();
  });
});

it("does not send the stale timestamp when editing", async () => {
  const api = installFakeApi();
  api.concepts["tables/orders"].frontmatter.timestamp = "2020-01-01T00:00:00Z";
  window.location.hash = "#/e/tables/orders";
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "Save" }));
  await waitFor(() => expect(api.calls.some((c) => c.method === "PATCH")).toBe(true));
  expect(api.calls.find((c) => c.method === "PATCH")!.body!.frontmatter).not.toHaveProperty("timestamp");
});

describe("workspaces", () => {
  it("lists workspaces and opens an index", async () => {
    const api = installFakeApi({ workspaces: true });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Workspaces" })).toBeInTheDocument();
    expect(screen.getByText("empty")).toBeInTheDocument();
    await user.click(await screen.findByRole("link", { name: "notes" }));
    expect(window.location.hash).toBe("#/w/work/notes/");
    expect(await screen.findByRole("heading", { name: "(root)" })).toBeInTheDocument();
    expect(api.calls.some((c) => c.url === "/api/workspaces/work/indexes/notes/tree?dir=")).toBe(true);
    expect(screen.getByRole("link", { name: "work / notes" })).toBeInTheDocument();
  });

  it("scopes concept links to the index", async () => {
    const api = installFakeApi({ workspaces: true });
    const user = userEvent.setup();
    window.location.hash = "#/w/work/notes/d/tables";
    render(<App />);
    const leaf = await within(screen.getByRole("navigation")).findByRole("link", { name: "Orders" });
    expect(leaf).toHaveAttribute("href", "#/w/work/notes/c/tables/orders");
    await user.click(leaf);
    expect(await screen.findByRole("heading", { name: "Orders" })).toBeInTheDocument();
    expect(api.calls.some((c) => c.url === "/api/workspaces/work/indexes/notes/concepts/tables/orders")).toBe(true);
  });

  it("creates a workspace and an index", async () => {
    const api = installFakeApi({ workspaces: true });
    const user = userEvent.setup();
    const prompt = vi.spyOn(window, "prompt");
    render(<App />);
    prompt.mockReturnValueOnce("fresh");
    await user.click(await screen.findByRole("button", { name: "New workspace" }));
    await waitFor(() => expect(api.workspaces.some((w) => w.name === "fresh")).toBe(true));
    prompt.mockReturnValueOnce("mem");
    await user.click(await screen.findByRole("button", { name: "New index in fresh" }));
    await waitFor(() => expect(api.workspaces.find((w) => w.name === "fresh")!.indexes).toEqual([{ name: "mem", description: null }]));
    expect(await screen.findByRole("link", { name: "mem" })).toBeInTheDocument();
  });

  it("hides creation controls when read-only", async () => {
    installFakeApi({ workspaces: true, readOnly: true });
    render(<App />);
    await screen.findByRole("heading", { name: "Workspaces" });
    expect(screen.queryByRole("button", { name: "New workspace" })).toBeNull();
  });
});

describe("tree view", () => {
  const nav = () => within(screen.getByRole("navigation"));

  it("reveals and highlights the open concept on a deep link", async () => {
    installFakeApi();
    window.location.hash = "#/c/tables/orders";
    render(<App />);
    const leaf = await nav().findByRole("link", { name: "Orders" });
    expect(leaf).toHaveAttribute("aria-current", "page");
    expect(nav().getByRole("link", { name: "Users" })).not.toHaveAttribute("aria-current");
  });

  it("highlights the open directory", async () => {
    installFakeApi();
    window.location.hash = "#/d/tables";
    render(<App />);
    expect(await nav().findByRole("link", { name: "tables" })).toHaveAttribute("aria-current", "page");
  });

  it("collapses everything", async () => {
    installFakeApi();
    window.location.hash = "#/c/tables/orders";
    const user = userEvent.setup();
    render(<App />);
    await nav().findByRole("link", { name: "Orders" });
    await user.click(screen.getByRole("button", { name: "Collapse all" }));
    expect(nav().queryByRole("link", { name: "Orders" })).toBeNull();
    expect(nav().getByRole("button", { name: "Toggle tables" })).toHaveAttribute("aria-expanded", "false");
  });

  it("exposes tree semantics and keyboard expand/collapse", async () => {
    installFakeApi();
    const user = userEvent.setup();
    render(<App />);
    const dir = await nav().findByRole("link", { name: "tables" });
    expect(screen.getByRole("tree")).toBeInTheDocument();
    dir.focus();
    await user.keyboard("{ArrowRight}");
    const orders = await nav().findByRole("link", { name: "Orders" });
    await user.keyboard("{ArrowDown}");
    expect(orders).toHaveFocus();
    await user.keyboard("{ArrowLeft}"); // from a leaf: back to its parent directory
    expect(dir).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(nav().queryByRole("link", { name: "Orders" })).toBeNull();
  });
});

describe("index description", () => {
  it("lists index descriptions on the workspaces page", async () => {
    installFakeApi({ workspaces: true });
    render(<App />);
    expect(await screen.findByText(/Meeting notes/)).toBeInTheDocument();
  });

  it("shows the open index's description in the header", async () => {
    installFakeApi({ workspaces: true });
    window.location.hash = "#/w/work/notes/";
    render(<App />);
    const header = screen.getByRole("banner");
    expect(await within(header).findByText("Meeting notes")).toBeInTheDocument();
  });

  it("edits the index description via the bundle describe route", async () => {
    const api = installFakeApi({ workspaces: true });
    vi.spyOn(window, "prompt").mockReturnValue("New purpose");
    const user = userEvent.setup();
    window.location.hash = "#/w/work/notes/";
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Edit index description" }));
    expect(await within(screen.getByRole("banner")).findByText("New purpose")).toBeInTheDocument();
    const call = api.calls.find((c) => c.url === "/api/workspaces/work/indexes/notes/bundle/describe")!;
    expect(call.method).toBe("POST");
    expect(call.body).toEqual({ description: "New purpose" });
  });

  it("an empty prompt clears the description", async () => {
    const api = installFakeApi({ workspaces: true });
    vi.spyOn(window, "prompt").mockReturnValue("");
    const user = userEvent.setup();
    window.location.hash = "#/w/work/notes/";
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Edit index description" }));
    expect(await within(screen.getByRole("banner")).findByText("No description")).toBeInTheDocument();
    expect(api.calls.find((c) => c.url.endsWith("/bundle/describe"))!.body).toEqual({ description: null });
  });

  it("a cancelled prompt changes nothing", async () => {
    const api = installFakeApi({ workspaces: true });
    vi.spyOn(window, "prompt").mockReturnValue(null);
    const user = userEvent.setup();
    window.location.hash = "#/w/work/notes/";
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Edit index description" }));
    expect(api.calls.some((c) => c.url.endsWith("/bundle/describe"))).toBe(false);
  });

  it("hides the edit control when read-only", async () => {
    installFakeApi({ workspaces: true, readOnly: true });
    window.location.hash = "#/w/work/notes/";
    render(<App />);
    expect(await within(screen.getByRole("banner")).findByText("Meeting notes")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit index description" })).toBeNull();
  });

  it("renders a description search hit linking to the index root", async () => {
    installFakeApi({ workspaces: true, search: true });
    const user = userEvent.setup();
    window.location.hash = "#/w/work/notes/";
    render(<App />);
    await user.type(await screen.findByRole("searchbox"), "meetings{Enter}");
    const main = screen.getByRole("main");
    const link = await within(main).findByRole("link", { name: "index notes" });
    expect(link.getAttribute("href")).toBe("#/w/work/notes/d/");
    expect(within(main).getByText("Meeting notes excerpt")).toBeInTheDocument();
  });
});
