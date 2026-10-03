import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Brand from "@/components/app/Brand";

describe("Brand", () => {
  it("shows the XPAND logo and links home", () => {
    render(<Brand />);
    expect(screen.getByRole("link", { name: "XPAND Availability home" })).toHaveAttribute("href", expect.stringMatching(/dashboard/));
    expect(screen.getByAltText("XPAND")).toHaveAttribute("src", expect.stringContaining("xpand-logo.svg"));
    expect(screen.getByText("Availability")).toBeInTheDocument();
  });
});
