import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../test/setup";
import { Landing } from "./Landing";

const GITHUB = "https://api.github.com/repos/hannguyendd/okf-sdk";
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*" };

describe("landing page", () => {
  beforeEach(() => {
    sessionStorage.clear();
    server.use(
      http.options(GITHUB, () => new HttpResponse(null, { status: 204, headers: CORS })),
      http.get(GITHUB, () => HttpResponse.json({ stargazers_count: 1234 }, { headers: CORS })),
    );
  });

  it("shows the live GitHub star count in the header", async () => {
    render(<Landing />);
    const star = await screen.findByRole("link", { name: "Star Okie on GitHub (1234 stars)" });
    expect(star).toHaveAttribute("href", "https://github.com/hannguyendd/okf-sdk");
    expect(star).toHaveTextContent("1.2K");
  });

  it("still offers a Star button when GitHub can’t be reached", async () => {
    server.use(http.get(GITHUB, () => HttpResponse.json({}, { status: 403, headers: CORS })));
    render(<Landing />);
    expect(screen.getByRole("link", { name: "Star Okie on GitHub" })).toHaveTextContent("Star");
  });

  it("says what Okie does and how to start", () => {
    render(<Landing />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("OK, fine. I’ll remember it for you.");
    expect(screen.getByRole("heading", { name: "Wake Okie up (about 2 minutes)" })).toBeInTheDocument();
    expect(screen.getByText(/uv run okf-web --static packages\/okf-web2\/dist/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Wake Okie up" })[0]).toHaveAttribute("href", "#start");
  });

  it("switches screenshots with the tabs", async () => {
    const user = userEvent.setup();
    render(<Landing />);
    const tabs = within(screen.getByRole("tablist", { name: "Screenshots" }));
    await user.click(tabs.getByRole("tab", { name: "Night shift" }));
    expect(tabs.getByRole("tab", { name: "Night shift" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Chalkboard dark mode");
  });
});
