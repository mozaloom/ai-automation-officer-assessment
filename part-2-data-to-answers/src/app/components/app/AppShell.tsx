import AppSidebar from "./AppSidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh">
      <AppSidebar />
      <main id="main" className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 pb-24 pt-20 sm:px-6 lg:px-10 lg:pb-10 lg:pt-8">{children}</main>
    </div>
  );
}
