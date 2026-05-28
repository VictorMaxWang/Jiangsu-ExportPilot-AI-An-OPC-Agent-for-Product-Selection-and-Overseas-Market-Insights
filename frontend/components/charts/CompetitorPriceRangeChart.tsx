"use client";

import { useMemo } from "react";
import type { DashboardPriceRange } from "../../app/_lib/api-client";
import { BaseEChart } from "./BaseEChart";
import { buildPriceRangeOption } from "./chart-options";

type CompetitorPriceRangeChartProps = {
  items: DashboardPriceRange[];
};

export function CompetitorPriceRangeChart({ items }: CompetitorPriceRangeChartProps) {
  const option = useMemo(() => {
    const chartItems = items.map((item) => ({
      label: `${item.country} · ${item.product_name}`,
      min: toNumber(item.min_price),
      median: toNumber(item.median_price),
      avg: toNumber(item.avg_price),
      max: toNumber(item.max_price),
      currency: item.currency || "",
    }));
    return buildPriceRangeOption(chartItems);
  }, [items]);

  return <BaseEChart option={option} />;
}

function toNumber(value: string | number | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
