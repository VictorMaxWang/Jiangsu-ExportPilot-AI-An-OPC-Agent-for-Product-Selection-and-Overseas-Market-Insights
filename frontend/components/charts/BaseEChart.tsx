"use client";

import type { ECharts, EChartsOption } from "echarts";
import * as echarts from "echarts";
import { useEffect, useRef } from "react";

type BaseEChartProps = {
  option: EChartsOption;
  className?: string;
  height?: number;
};

export function BaseEChart({ option, className, height = 320 }: BaseEChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    chartRef.current = echarts.init(containerRef.current);
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const resizeObserver = new ResizeObserver(() => {
      chartRef.current?.resize();
    });
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  return <div ref={containerRef} className={className} style={{ height }} />;
}
