import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const router = { replace: vi.fn(), push: vi.fn() };
let pathname = "/dashboard/";
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => pathname, useSearchParams: () => search }));

const sessionState: { session: unknown; ready: boolean; signIn: ReturnType<typeof vi.fn>; signOut: ReturnType<typeof vi.fn> } = { session: null, ready: true, signIn: vi.fn(), signOut: vi.fn() };
vi.mock("@/lib/auth/SessionProvider", () => ({ useSession: () => sessionState }));

import AuthGuard from "@/components/auth/AuthGuard";
import LoginForm from "@/components/auth/LoginForm";
import { friendlyAuthError } from "@/lib/auth/cognito";

beforeEach(() => { router.replace.mockReset(); sessionState.session = null; sessionState.ready = true; sessionState.signIn = vi.fn(); pathname = "/dashboard/"; search = new URLSearchParams(); });

describe("AuthGuard", () => {
  it("shows a spinner and sends visitors to sign in, remembering the page", async () => {
    render(<AuthGuard><p>secret</p></AuthGuard>);
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login/?next=%2Fdashboard%2F"));
  });
  it("waits for the session to load before deciding", () => {
    sessionState.ready = false;
    render(<AuthGuard><p>secret</p></AuthGuard>);
    expect(router.replace).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
  it("renders the app for a signed-in user", () => {
    sessionState.session = { email: "a@b.co" };
    render(<AuthGuard><p>secret</p></AuthGuard>);
    expect(screen.getByText("secret")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("LoginForm", () => {
  const fill = async (email = "demo@xpand.medgan.ai", password = "pw") => {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email"), email);
    await user.type(screen.getByLabelText("Password", { exact: true }), password);
    return user;
  };

  it("keeps the button disabled until both fields are filled", async () => {
    render(<LoginForm />);
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
    await fill();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });
  it("signs in and goes to the dashboard", async () => {
    sessionState.signIn.mockResolvedValue(undefined);
    render(<LoginForm />);
    const user = await fill();
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(sessionState.signIn).toHaveBeenCalledWith("demo@xpand.medgan.ai", "pw");
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/dashboard/"));
  });
  it("returns to the page the user came from, but never to another site", async () => {
    sessionState.signIn.mockResolvedValue(undefined);
    search = new URLSearchParams("next=/assistant/");
    const first = render(<LoginForm />);
    await (await fill()).click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/assistant/"));
    first.unmount();
    router.replace.mockReset();
    search = new URLSearchParams("next=//evil.example.com");
    render(<LoginForm />);
    await (await fill()).click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/dashboard/"));
  });
  it("shows a friendly error and does not navigate on failure", async () => {
    sessionState.signIn.mockRejectedValue(Object.assign(new Error("raw"), { code: "NotAuthorizedException" }));
    render(<LoginForm />);
    await (await fill()).click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
    expect(router.replace).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });
  it("can reveal the password", async () => {
    render(<LoginForm />);
    const user = userEvent.setup();
    expect(screen.getByLabelText("Password", { exact: true })).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(screen.getByLabelText("Password", { exact: true })).toHaveAttribute("type", "text");
  });
});

describe("friendlyAuthError", () => {
  it.each([
    ["NotAuthorizedException", "Incorrect email or password."],
    ["UserNotFoundException", "Incorrect email or password."],
    ["NewPasswordRequired", "A new password is required"],
    ["TooManyRequestsException", "Too many attempts"],
    ["NetworkError", "Could not reach"],
  ])("%s", (code, text) => expect(friendlyAuthError({ code })).toContain(text));
  it("never leaks unknown details beyond the message", () => {
    expect(friendlyAuthError(new Error("Something odd"))).toBe("Something odd");
    expect(friendlyAuthError({})).toBe("Sign-in failed. Please try again.");
  });
});
