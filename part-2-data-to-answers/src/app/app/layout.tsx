import type { Metadata, Viewport } from "next";
import { Providers } from "@/lib/Providers";
import { plusJakartaSans } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "XPAND Availability",
  description: "Where products are available, answered from the latest POS data.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={plusJakartaSans.variable}>
      <body className="font-sans antialiased">
        <a href="#main" className="skip-nav">Skip to content</a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
