"use client";

import type { ReactNode } from "react";
import { LicenseProvider } from "@/context/LicenseProvider";

export function Providers({ children }: { children: ReactNode }) {
  return <LicenseProvider>{children}</LicenseProvider>;
}
