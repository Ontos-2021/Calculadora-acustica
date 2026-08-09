"use client";

import { useEffect, useRef, useState } from "react";
import { BarChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { init, use, type EChartsCoreOption, type EChartsType } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  HeatmapChart,
  ScatterChart,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  AriaComponent,
]);

export function EChart({
  option,
  className = "h-[clamp(20rem,55vw,24rem)]",
  notMerge = true,
  lazyUpdate = true,
}: {
  option: EChartsCoreOption;
  className?: string;
  notMerge?: boolean;
  lazyUpdate?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const update = () => setDark(root.classList.contains("dark"));
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = init(container, dark ? "dark" : undefined, { renderer: "canvas" });
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(() => {
      if (container.clientWidth > 0 && container.clientHeight > 0) chart.resize();
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, [dark]);

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge, lazyUpdate });
  }, [option, notMerge, lazyUpdate, dark]);

  return <div ref={containerRef} className={`echarts-for-react min-w-0 w-full ${className}`} />;
}
