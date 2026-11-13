import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Landing } from "./Landing";

describe("landing page", () => {
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
