import Image from "next/image";
import Link from "next/link";

/** XPAND wordmark (brand asset supplied by the team) with the product name underneath. */
export default function Brand({ size = "md", href = "/dashboard/" }: { size?: "sm" | "md"; href?: string }) {
  const height = size === "md" ? 38 : 28;
  return (
    <Link href={href} aria-label="XPAND Availability home" className="inline-flex flex-col gap-1">
      <Image src="/logos/xpand-logo.svg" alt="XPAND" width={Math.round(height * (614.91 / 141.9))} height={height} priority style={{ height, width: "auto" }} />
      <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-gray">Availability</span>
    </Link>
  );
}
