import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

const variants = {
  info: "border-sky-200 bg-sky-50 text-sky-950 dark:border-sky-900 dark:bg-sky-950/35 dark:text-sky-100",
  success: "border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/35 dark:text-emerald-100",
  warning: "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-100",
  danger: "border-rose-200 bg-rose-50 text-rose-950 dark:border-rose-900 dark:bg-rose-950/35 dark:text-rose-100",
};

export function Alert({ variant = "info", className, ...props }: HTMLAttributes<HTMLDivElement> & { variant?: keyof typeof variants }) {
  return <div className={cn("rounded-lg border p-3 text-sm", variants[variant], className)} {...props} />;
}
