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

const tree = () => within(screen.getByRole("navigation", { name: "Bundle tree" }));

describe("workspaces", () => {
  it("lists workspaces and opens the workspace page with its notebooks", async () => {
    const { user } = start("#/");
    expect(await screen.findByText("OK, fine, I’ll remember it for you.")).toBeInTheDocument();
    await user.click(await screen.findByRole("link", { name: /team/ }));
    const notes = await screen.findByRole("article", { name: "Index notes" });
    expect(await within(notes).findByText(/3 concepts/)).toBeInTheDocument();
    const recent = await screen.findByRole("region", { name: "Recently remembered" });
    // newest first, across indexes
    const items = within(recent).getAllByRole("link").map((a) => a.textContent);
    expect(items).toEqual(["Users", "Orders", "Readme"]);
  });

  it("saves a workspace colour", async () => {
    const { user, backend } = start("#/w/team");
    const picker = await screen.findByRole("radiogroup", { name: "Colour of team" });
    await user.click(within(picker).getByRole("radio", { name: "purple" }));
    await waitFor(() => expect(backend.workspaces.team.color).toBe("purple"));
  });

  it("creates an index from the workspace page", async () => {
    const { user, backend } = start("#/w/team");
    await user.click(await screen.findByRole("button", { name: "New index" }));
    await user.type(screen.getByLabelText("Index name"), "ideas");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByRole("article", { name: "Index ideas" })).toBeInTheDocument();
    expect(backend.workspaces.team.indexes.ideas).toBeDefined();
  });
});

describe("index", () => {
  it("browses the explorer to a concept", async () => {
    const { user } = start("#/w/team/notes");
    await user.click(await tree().findByRole("link", { name: "tables" }));
    expect(await screen.findByRole("heading", { name: "tables" })).toBeInTheDocument();
    await user.click(await tree().findByRole("link", { name: "Orders" }));
    expect(await screen.findByRole("heading", { name: "Orders" })).toBeInTheDocument();
    expect(screen.getByText("tables/orders")).toBeInTheDocument();
  });

  it("toggles a directory open from the explorer", async () => {
    const { user } = start("#/w/team/notes");
    await user.click(await screen.findByRole("button", { name: "Toggle tables" }));
    expect(await tree().findByRole("link", { name: "Users" })).toBeInTheDocument();
  });

  it("goes back to the front page from the explorer label and folds all folders", async () => {
    const { user } = start("#/w/team/notes/c/tables/orders");
    expect(await tree().findByRole("link", { name: "Users" })).toBeInTheDocument();
    await user.click(tree().getByRole("button", { name: "Fold all folders" }));
    await waitFor(() => expect(tree().queryByRole("link", { name: "Users" })).not.toBeInTheDocument());
    await user.click(tree().getByRole("link", { name: "Front page" }));
    await waitFor(() => expect(window.location.hash).toBe("#/w/team/notes/"));
  });

  it("creates a folder with a description and lands in it", async () => {
    const { user, backend } = start("#/w/team/notes");
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
    const { user, backend } = start("#/w/team/notes/c/tables/orders");
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const body = await screen.findByLabelText("Body");
    await user.clear(body);
    await user.type(body, "new text");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("new text")).toBeInTheDocument();
    expect(backend.workspaces.team.indexes.notes.concepts["tables/orders"].body).toBe("new text");
    expect(await screen.findByText("Fine. Remembered.")).toBeInTheDocument();
  });

  it("asks before erasing a concept other pages link to", async () => {
    const { user, backend } = start("#/w/team/notes/c/tables/users");
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await user.click(await screen.findByRole("button", { name: "Erase" }));
    expect(await screen.findByText("Other pages link here")).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).getByText("tables/orders")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Erase anyway" }));
    await waitFor(() => expect(backend.workspaces.team.indexes.notes.concepts["tables/users"]).toBeUndefined());
    expect(await screen.findByRole("heading", { name: "tables" })).toBeInTheDocument();
  });

  it("shows an empty notebook kindly", async () => {
    start("#/w/team/empty");
    expect(await screen.findByText("Nothing here yet. Tell me something and I’ll remember it.")).toBeInTheDocument();
  });

  it("says search is napping without calling it when embeddings are off", async () => {
    const { backend } = start("#/w/team/notes/s/orders");
    expect(await screen.findByText(/Search is napping/)).toBeInTheDocument();
    expect(backend.calls.some((c) => c.path.includes("/search"))).toBe(false);
  });

  it("shows search hits when enabled", async () => {
    start("#/w/team/notes/s/orders", { search: true });
    expect(await screen.findByText("Orders and users")).toBeInTheDocument();
    expect(screen.getByText("0.91")).toBeInTheDocument();
  });

  it("hides write actions when read-only", async () => {
    start("#/w/team/notes", { readOnly: true });
    expect(await screen.findByText("read-only")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New folder" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reindex" })).not.toBeInTheDocument();
  });
});

describe("concept page", () => {
  it("shows the timestamp as a readable date, not raw ISO", async () => {
    start("#/w/team/notes/c/tables/orders");
    expect(await screen.findByText("last updated")).toBeInTheDocument();
    const time = document.querySelector("time")!;
    expect(time).toHaveAttribute("dateTime", "2026-11-10T10:00:00Z");
    expect(time.textContent).toMatch(/^Nov 10, 2026, .+ · /);
    expect(screen.queryByText("2026-11-10T10:00:00Z")).not.toBeInTheDocument();
  });
});

describe("navigation and moving", () => {
  it("climbs back to the index root from a nested page via the breadcrumb", async () => {
    const { user } = start("#/w/team/notes/c/tables/orders");
    const crumbs = within(await screen.findByRole("navigation", { name: "Breadcrumb" }));
    await user.click(crumbs.getByRole("link", { name: /notes/ }));
    expect(await screen.findByRole("heading", { name: "notes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New folder" })).toBeInTheDocument();
  });

  it("shows which pages link to a concept", async () => {
    start("#/w/team/notes/c/tables/users");
    const linkedFrom = within(await screen.findByRole("region", { name: "Linked from" }));
    expect(linkedFrom.getByRole("link", { name: "tables/orders" })).toBeInTheDocument();
  });

  it("moves a concept into another folder with the folder picker", async () => {
    const { user, backend } = start("#/w/team/notes/c/readme");
    await user.click(await screen.findByRole("button", { name: "Move" }));
    await waitFor(() => expect(screen.getByRole("option", { name: "tables" })).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText("Folder"), "tables");
    await user.click(screen.getByRole("button", { name: "Move" }));
    await waitFor(() => expect(backend.workspaces.team.indexes.notes.concepts["tables/readme"]).toBeDefined());
    expect(window.location.hash).toBe("#/w/team/notes/c/tables/readme");
  });

  it("moves a concept by dragging it onto a folder in the explorer", async () => {
    const { backend } = start("#/w/team/notes");
    const nav = within(screen.getByRole("navigation", { name: "Bundle tree" }));
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
    await waitFor(() => expect(backend.workspaces.team.indexes.notes.concepts["tables/readme"]).toBeDefined());
    expect(backend.workspaces.team.indexes.notes.concepts.readme).toBeUndefined();
  });
});

describe("routing", () => {
  it("shows the lost page for unknown routes", async () => {
    start("#/nowhere/at/all");
    expect(await screen.findByText(/This page fell out of the notebook/)).toBeInTheDocument();
  });
});
