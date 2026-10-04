import localFont from "next/font/local";
import { IBM_Plex_Sans_Arabic } from "next/font/google";

// Plus Jakarta Sans (Latin) and IBM Plex Sans Arabic: the same faces as the Clarity front end.
export const plusJakartaSans = localFont({
  src: [
    { path: "../public/fonts/PlusJakartaSans-Regular.woff2", weight: "400", style: "normal" },
    { path: "../public/fonts/PlusJakartaSans-Bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-inter",
  display: "swap",
  preload: true,
});

export const ibmPlexSansArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  variable: "--font-arabic",
  display: "swap",
  weight: ["400", "700"],
});

export const fontVariables = `${plusJakartaSans.variable} ${ibmPlexSansArabic.variable}`;
