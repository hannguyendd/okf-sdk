import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { createBackend } from "./test/fakeBackend";
import { server } from "./test/setup";

function start(hash: string, opts: Parameters<typeof createBackend>[0] = {}) {
  const backend = createBackend(opts);
  server.use(backend.handler);
  window.location.hash = hash;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<App client={client} />);
  return { backend, user: userEvent.setup() };
}

const tree = () => within(screen.getByRole("navigation", { name: "Workspace tree" }));

describe("workspaces", () => {
  it("lists workspaces and opens the workspace page with its overview", async () => {
    const { user } = start("#/");
    expect(await screen.findByText("OK, fine, I’ll remember it for you.")).toBeInTheDocument();
    await user.click(await screen.findByRole("link", { name: /^w\b/ }));
    expect(await screen.findByText(/3 concepts/)).toBeInTheDocument();
    const recent = await screen.findByRole("region", { name: "Recently remembered" });
    // newest first
    const items = within(recent).getAllByRole("link").map((a) => a.textContent);
    expect(items).toEqual(["Users", "Orders", "Readme"]);
    expect(window.location.hash).toBe("#/w/w");
  });

  it("shows the root tree for a workspace with no index picker", async () => {
    const { backend } = start("#/w/w/");
    expect(await tree().findByRole("link", { name: "tables" })).toBeInTheDocument();
    expect(tree().getByRole("link", { name: "Readme" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "w" })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByText("Meeting notes")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /New index/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("article", { name: /^Index / })).not.toBeInTheDocument();
    expect(backend.calls.some((c) => c.path.includes("/indexes") || c.path.includes("/bundle"))).toBe(false);
  });

  it("lists an unmigrated workspace with what to run, next to the working ones", async () => {
    const { backend } = start("#/", { v1: true });
    const old = await screen.findByRole("region", { name: "Workspace old" });
    expect(within(old).getByText(/run okf-migrate-v2/)).toBeInTheDocument();
    expect(within(old).queryByRole("radiogroup")).not.toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Workspace w" })).toBeInTheDocument();
    expect(await screen.findByText("Meeting notes")).toBeInTheDocument();
    expect(backend.calls.some((c) => c.path.startsWith("/api/workspaces/old/"))).toBe(false);
  });

  it("saves a workspace colour", async () => {
    const { user, backend } = start("#/w/w");
    const picker = await screen.findByRole("radiogroup", { name: "Colour of w" });
    await user.click(within(picker).getByRole("radio", { name: "purple" }));
    await waitFor(() => expect(backend.workspaces.w.color).toBe("purple"));
  });

  it("creates a folder from the workspace page", async () => {
    const { user, backend } = start("#/w/w/");
    await user.click(await screen.findByRole("button", { name: "New folder" }));
    await user.type(screen.getByLabelText("Folder name"), "ideas");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("heading", { name: "ideas" })).toBeInTheDocument();
    const call = backend.calls.find((c) => c.method === "POST" && c.path === "/api/workspaces/w/dirs");
    expect(call?.body).toEqual({ dir: "ideas", description: "" });
    expect(backend.workspaces.w.dirs.has("ideas")).toBe(true);
  });

  it("edits the workspace description as the root directory description", async () => {
    const { user, backend } = start("#/w/w/");
    await user.click(await screen.findByRole("button", { name: "Edit workspace description" }));
    const field = screen.getByLabelText("Workspace description (empty clears it)");
    await user.clear(field);
    await user.type(field, "Team memory");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(backend.workspaces.w.descriptions[""]).toBe("Team memory"));
    expect(backend.calls.find((c) => c.path === "/api/workspaces/w/describe")?.body).toEqual({ dir: "", description: "Team memory" });
  });

  it("describes a fresh workspace whose root has no listing yet", async () => {
    const { user, backend } = start("#/w/empty/");
    await user.click(await screen.findByRole("button", { name: "Edit workspace description" }));
    await user.type(screen.getByLabelText("Workspace description (empty clears it)"), "Fresh start");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(backend.workspaces.empty.descriptions[""]).toBe("Fresh start"));
    expect(await screen.findByText("Noted.")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("workspace pages", () => {
  it("browses the explorer to a concept", async () => {
    const { user } = start("#/w/w/");
    await user.click(await tree().findByRole("link", { name: "tables" }));
    expect(await screen.findByRole("heading", { name: "tables" })).toBeInTheDocument();
    await user.click(await tree().findByRole("link", { name: "Orders" }));
    expect(await screen.findByRole("heading", { name: "Orders" })).toBeInTheDocument();
    expect(screen.getByText("tables/orders")).toBeInTheDocument();
  });

  it("toggles a directory open from the explorer", async () => {
    const { user } = start("#/w/w/");
    await user.click(await screen.findByRole("button", { name: "Toggle tables" }));
    expect(await tree().findByRole("link", { name: "Users" })).toBeInTheDocument();
  });

  it("goes back to the front page from the explorer label and folds all folders", async () => {
    const { user } = start("#/w/w/c/tables/orders");
    expect(await tree().findByRole("link", { name: "Users" })).toBeInTheDocument();
    await user.click(tree().getByRole("button", { name: "Fold all folders" }));
    await waitFor(() => expect(tree().queryByRole("link", { name: "Users" })).not.toBeInTheDocument());
    await user.click(tree().getByRole("link", { name: "Front page" }));
    await waitFor(() => expect(window.location.hash).toBe("#/w/w/"));
  });

  it("creates a folder with a description and lands in it", async () => {
    const { user, backend } = start("#/w/w/");
    await user.click(await screen.findByRole("button", { name: "New folder" }));
    await user.type(screen.getByLabelText("Folder name"), "guides");
    await user.type(screen.getByLabelText("What goes in it? (optional)"), "How-tos");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("heading", { name: "guides" })).toBeInTheDocument();
    expect(backend.calls.find((c) => c.path.endsWith("/dirs"))?.body).toEqual({ dir: "guides", description: "How-tos" });
    expect(await tree().findByRole("link", { name: "guides" })).toBeInTheDocument();
    expect(await screen.findByText("Folder’s ready. Fill it whenever.")).toBeInTheDocument();
  });

  it("edits a concept and says so", async () => {
    const { user, backend } = start("#/w/w/c/tables/orders");
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const body = await screen.findByLabelText("Body");
    await user.clear(body);
    await user.type(body, "new text");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("new text")).toBeInTheDocument();
    expect(backend.workspaces.w.concepts["tables/orders"].body).toBe("new text");
    expect(await screen.findByText("Fine. Remembered.")).toBeInTheDocument();
  });

  it("asks before erasing a concept other pages link to", async () => {
    const { user, backend } = start("#/w/w/c/tables/users");
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await user.click(await screen.findByRole("button", { name: "Erase" }));
    expect(await screen.findByText("Other pages link here")).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).getByText("tables/orders")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Erase anyway" }));
    await waitFor(() => expect(backend.workspaces.w.concepts["tables/users"]).toBeUndefined());
    expect(await screen.findByRole("heading", { name: "tables" })).toBeInTheDocument();
  });

  it("shows an empty notebook kindly", async () => {
    start("#/w/empty/");
    expect(await screen.findByText("Nothing here yet. Tell me something and I’ll remember it.")).toBeInTheDocument();
  });

  it("says search is napping without calling it when embeddings are off", async () => {
    const { backend } = start("#/w/w/search/orders");
    expect(await screen.findByText(/Search is napping/)).toBeInTheDocument();
    expect(backend.calls.some((c) => c.path.includes("/search"))).toBe(false);
  });

  it("shows search hits when enabled and links them to their directory", async () => {
    const { user, backend } = start("#/w/w/search/orders", { search: true });
    expect(await screen.findByText("Orders and users")).toBeInTheDocument();
    expect(screen.getByText("0.91")).toBeInTheDocument();
    expect(backend.calls.find((c) => c.path.includes("/search"))?.path).toBe("/api/workspaces/w/search?q=orders&top_k=10");
    await user.click(within(screen.getByRole("main")).getByRole("link", { name: "tables" }));
    await waitFor(() => expect(window.location.hash).toBe("#/w/w/d/tables"));
  });

  it("searches from the header box", async () => {
    const { user } = start("#/w/w/", { search: true });
    await user.type(await screen.findByRole("searchbox", { name: "Search" }), "orders{Enter}");
    await waitFor(() => expect(window.location.hash).toBe("#/w/w/search/orders"));
  });

  it("hides write actions when read-only", async () => {
    start("#/w/w/", { readOnly: true });
    expect(await screen.findByText("read-only")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New folder" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reindex" })).not.toBeInTheDocument();
  });
});

describe("concept page", () => {
  it("shows the timestamp as a readable date, not raw ISO", async () => {
    start("#/w/w/c/tables/orders");
    expect(await screen.findByText("last updated")).toBeInTheDocument();
    const time = document.querySelector("time")!;
    expect(time).toHaveAttribute("dateTime", "2026-11-10T10:00:00Z");
    expect(time.textContent).toMatch(/^Nov 10, 2026, .+ · /);
    expect(screen.queryByText("2026-11-10T10:00:00Z")).not.toBeInTheDocument();
  });
});

describe("navigation and moving", () => {
  it("climbs back to the workspace root from a nested page via the breadcrumb", async () => {
    const { user } = start("#/w/w/c/tables/orders");
    const crumbs = within(await screen.findByRole("navigation", { name: "Breadcrumb" }));
    await user.click(crumbs.getByRole("link", { name: /\bw$/ }));
    expect(await screen.findByRole("heading", { name: "w" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New folder" })).toBeInTheDocument();
  });

  it("shows which pages link to a concept", async () => {
    start("#/w/w/c/tables/users");
    const linkedFrom = within(await screen.findByRole("region", { name: "Linked from" }));
    expect(linkedFrom.getByRole("link", { name: "tables/orders" })).toBeInTheDocument();
  });

  it("moves a concept into another folder with the folder picker", async () => {
    const { user, backend } = start("#/w/w/c/readme");
    await user.click(await screen.findByRole("button", { name: "Move" }));
    await waitFor(() => expect(screen.getByRole("option", { name: "tables" })).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText("Folder"), "tables");
    await user.click(screen.getByRole("button", { name: "Move" }));
    await waitFor(() => expect(backend.workspaces.w.concepts["tables/readme"]).toBeDefined());
    expect(window.location.hash).toBe("#/w/w/c/tables/readme");
  });

  it("moves a concept by dragging it onto a folder in the explorer", async () => {
    const { backend } = start("#/w/w/");
    const nav = within(screen.getByRole("navigation", { name: "Workspace tree" }));
    const page = await nav.findByRole("link", { name: "Readme" });
    const folderRow = (await nav.findByRole("link", { name: "tables" })).parentElement!;
    const data = new Map<string, string>();
    const dataTransfer = {
      setData: (k: string, v: string) => data.set(k, v),
      getData: (k: string) => data.get(k) ?? "",
      get types() { return [...data.keys()]; },
      dropEffect: "none", effectAllowed: "all",
    };
    fireEvent.dragStart(page, { dataTransfer });
    fireEvent.dragOver(folderRow, { dataTransfer });
    fireEvent.drop(folderRow, { dataTransfer });
    await waitFor(() => expect(backend.workspaces.w.concepts["tables/readme"]).toBeDefined());
    expect(backend.workspaces.w.concepts.readme).toBeUndefined();
  });
});

describe("routing", () => {
  it("shows the lost page for unknown routes", async () => {
    start("#/nowhere/at/all");
    expect(await screen.findByText(/This page fell out of the notebook/)).toBeInTheDocument();
  });
});
