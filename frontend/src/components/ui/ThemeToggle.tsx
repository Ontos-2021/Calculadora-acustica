"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "./Button";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const saved = localStorage.getItem("acoustic-theme");
    const enabled = saved === "dark" || (!saved && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", enabled);
    setDark(enabled);
  }, []);
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("acoustic-theme", next ? "dark" : "light");
  }
  return <Button type="button" variant="ghost" size="icon" onClick={toggle} aria-label={dark ? "Usar tema claro" : "Usar tema oscuro"}>{dark ? <Sun className="size-4" /> : <Moon className="size-4" />}</Button>;
}
