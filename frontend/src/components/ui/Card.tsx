import { cn } from "@/lib/cn";

export function Card({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-[var(--radius-card)] border bg-surface p-4 shadow-[var(--shadow-panel)] sm:p-5", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h2 className={cn("mb-4 border-b pb-3 text-base font-semibold tracking-tight text-foreground", className)}>
      {children}
    </h2>
  );
}
