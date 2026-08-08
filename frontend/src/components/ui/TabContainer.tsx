"use client";

import { useState, type ReactNode } from "react";

interface Tab {
  key: string;
  label: string;
  badge?: string;
}

interface Props {
  tabs: Tab[];
  children: ReactNode[];
  defaultTab?: string;
}

export function TabContainer({ tabs, children, defaultTab }: Props) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.key || "");
  const childMap: Record<string, ReactNode> = {};
  tabs.forEach((t, i) => { childMap[t.key] = children[i]; });

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-1 border-b border-gray-200">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`px-3 py-2 text-xs font-medium transition-colors ${
              active === t.key
                ? "border-b-2 border-indigo-500 text-indigo-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
            {t.badge && (
              <span className="ml-1 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px]">
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>
      {childMap[active] || null}
    </div>
  );
}
