import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const router = { replace: vi.fn(), push: vi.fn() };
let pathname = "/en/dashboard/";
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => pathname, useSearchParams: () => search }));

const sessionState: { session: unknown; ready: boolean; signIn: ReturnType<typeof vi.fn>; signOut: ReturnType<typeof vi.fn> } = { session: null, ready: true, signIn: vi.fn(), signOut: vi.fn() };
vi.mock("@/lib/auth/SessionProvider", () => ({ useSession: () => sessionState }));

import AuthGuard from "@/components/auth/AuthGuard";
import LoginForm from "@/components/auth/LoginForm";
import { authErrorKey } from "@/lib/auth/cognito";
import { renderI18n as render } from "./render";

beforeEach(() => { router.replace.mockReset(); sessionState.session = null; sessionState.ready = true; sessionState.signIn = vi.fn(); pathname = "/en/dashboard/"; search = new URLSearchParams(); });

describe("AuthGuard", () => {
  it("shows a spinner and sends visitors to sign in, remembering the page", async () => {
    render(<AuthGuard><p>secret</p></AuthGuard>);
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/en/login/?next=%2Fen%2Fdashboard%2F"));
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
  const fill = async (email = "demo@xpandpros.com", password = "pw") => {
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
    expect(sessionState.signIn).toHaveBeenCalledWith("demo@xpandpros.com", "pw");
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/en/dashboard/"));
  });
  it("returns to the page the user came from, but never to another site", async () => {
    sessionState.signIn.mockResolvedValue(undefined);
    search = new URLSearchParams("next=/en/assistant/");
    const first = render(<LoginForm />);
    await (await fill()).click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/en/assistant/"));
    first.unmount();
    router.replace.mockReset();
    search = new URLSearchParams("next=//evil.example.com");
    render(<LoginForm />);
    await (await fill()).click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/en/dashboard/"));
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

describe("Arabic sign-in", () => {
  it("shows the form, the error and the password toggle in Arabic, and goes to the Arabic dashboard", async () => {
    sessionState.signIn.mockRejectedValueOnce(Object.assign(new Error("raw"), { code: "NotAuthorizedException" }));
    render(<LoginForm />, "ar");
    const user = userEvent.setup();
    expect(screen.getByRole("heading", { name: "تسجيل الدخول" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("البريد الإلكتروني"), "demo@xpandpros.com");
    await user.type(screen.getByLabelText("كلمة المرور", { exact: true }), "pw");
    await user.click(screen.getByRole("button", { name: "إظهار كلمة المرور" }));
    expect(screen.getByLabelText("كلمة المرور", { exact: true })).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: "تسجيل الدخول" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("البريد الإلكتروني أو كلمة المرور غير صحيحة.");
    sessionState.signIn.mockResolvedValue(undefined);
    await user.click(screen.getByRole("button", { name: "تسجيل الدخول" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/ar/dashboard/"));
  });
  it("only returns to a page in a supported language", async () => {
    sessionState.signIn.mockResolvedValue(undefined);
    search = new URLSearchParams("next=/fr/dashboard/");
    render(<LoginForm />, "ar");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("البريد الإلكتروني"), "a@b.co");
    await user.type(screen.getByLabelText("كلمة المرور", { exact: true }), "pw");
    await user.click(screen.getByRole("button", { name: "تسجيل الدخول" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/ar/dashboard/"));
  });
  it("sends signed-out visitors to the Arabic sign-in page", async () => {
    pathname = "/ar/assistant/";
    render(<AuthGuard><p>secret</p></AuthGuard>, "ar");
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/ar/login/?next=%2Far%2Fassistant%2F"));
  });
});

describe("authErrorKey", () => {
  it.each([
    ["NotAuthorizedException", "invalid"],
    ["UserNotFoundException", "invalid"],
    ["NewPasswordRequired", "newPassword"],
    ["TooManyRequestsException", "tooMany"],
    ["LimitExceededException", "tooMany"],
    ["NetworkError", "network"],
  ])("%s -> %s", (code, key) => expect(authErrorKey({ code })).toBe(key));
  it("recognises missing configuration and never leaks unknown details", () => {
    expect(authErrorKey(new Error("Sign-in is not configured (missing Cognito settings)."))).toBe("notConfigured");
    expect(authErrorKey(new Error("Something odd"))).toBe("generic");
    expect(authErrorKey({})).toBe("generic");
  });
});
