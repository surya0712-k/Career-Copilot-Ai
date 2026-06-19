import Link from "next/link";
import { ArrowLeft } from "lucide-react";

interface PageHeaderProps {
  backHref: string;
  backLabel?: string;
  title?: string;
  subtitle?: string;
}

export function PageHeader({ backHref, backLabel = "Back", title, subtitle }: PageHeaderProps) {
  return (
    <div className="mb-6">
      <Link
        href={backHref}
        className="mb-4 inline-flex min-h-[44px] items-center gap-2 text-sm text-white/60 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4 shrink-0" />
        {backLabel}
      </Link>
      {title && (
        <h1 className="text-xl font-bold leading-tight sm:text-2xl md:text-3xl">{title}</h1>
      )}
      {subtitle && <p className="mt-1 text-sm text-white/60">{subtitle}</p>}
    </div>
  );
}
