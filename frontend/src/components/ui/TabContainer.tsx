"use client";

import { Children, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

interface Tab {
  key: string;
  label: string;
  badge?: string;
}

interface Props {
  tabs: Tab[];
  children: ReactNode;
  defaultTab?: string;
  activeTab?: string;
  onTabChange?: (key: string) => void;
  label?: string;
  compact?: boolean;
}

export function TabContainer({
  tabs,
  children,
  defaultTab,
  activeTab,
  onTabChange,
  label = "Secciones del análisis",
  compact = false,
}: Props) {
  const generatedId = useId().replace(/:/g, "");
  const [internalActive, setInternalActive] = useState(defaultTab || tabs[0]?.key || "");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const active = activeTab ?? internalActive;
  const childArray = Children.toArray(children);

  function select(key: string) {
    if (activeTab === undefined) setInternalActive(key);
    onTabChange?.(key);
  }

  function keyboardNavigate(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let target = index;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") target = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") target = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") target = 0;
    else if (event.key === "End") target = tabs.length - 1;
    else return;
    event.preventDefault();
    select(tabs[target].key);
    tabRefs.current[target]?.focus();
  }

  const activeIndex = Math.max(0, tabs.findIndex((tab) => tab.key === active));
  const activeKey = tabs[activeIndex]?.key;

  return (
    <div>
      <div
        className={compact
          ? "scrollbar-thin mb-4 flex max-w-full gap-1 overflow-x-auto rounded-lg border bg-surface-muted p-1"
          : "scrollbar-thin sticky top-14 z-30 -mx-3 mb-5 flex max-w-[calc(100%+1.5rem)] gap-1 overflow-x-auto border-b bg-canvas/95 px-3 backdrop-blur sm:-mx-5 sm:max-w-[calc(100%+2.5rem)] sm:px-5 lg:static lg:mx-0 lg:max-w-full lg:rounded-lg lg:border lg:bg-surface lg:p-1"}
        role="tablist"
        aria-label={label}
      >
        {tabs.map((tab, index) => (
          <button
            key={tab.key}
            ref={(node) => { tabRefs.current[index] = node; }}
            id={`${generatedId}-tab-${tab.key}`}
            type="button"
            role="tab"
            aria-selected={activeKey === tab.key}
            aria-controls={`${generatedId}-panel-${tab.key}`}
            tabIndex={activeKey === tab.key ? 0 : -1}
            onClick={() => select(tab.key)}
            onKeyDown={(event) => keyboardNavigate(event, index)}
            className={`shrink-0 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${
              activeKey === tab.key
                ? "bg-teal-700 text-white shadow-sm dark:bg-teal-500 dark:text-zinc-950"
                : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-white"
            }`}
          >
            {tab.label}
            {tab.badge && (
              <span className="ml-1 rounded-full bg-zinc-200 px-1.5 py-0.5 text-[10px] text-zinc-900 dark:bg-zinc-700 dark:text-white">
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>
      <div
        id={`${generatedId}-panel-${activeKey}`}
        role="tabpanel"
        aria-labelledby={`${generatedId}-tab-${activeKey}`}
        tabIndex={0}
      >
        {childArray[activeIndex] ?? null}
      </div>
    </div>
  );
}
