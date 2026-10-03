import AppSidebar from "./AppSidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <AppSidebar />
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 pb-24 pt-16 sm:px-6 lg:px-8 lg:pb-8 lg:pt-6">{children}</main>
    </div>
  );
}
