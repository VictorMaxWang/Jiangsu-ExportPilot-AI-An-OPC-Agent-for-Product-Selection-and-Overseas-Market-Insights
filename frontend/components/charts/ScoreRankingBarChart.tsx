"use client";

import { useMemo } from "react";
import type { DashboardProductScore } from "../../app/_lib/api-client";
import { BaseEChart } from "./BaseEChart";
import { buildScoreRankingOption } from "./chart-options";

type ScoreRankingBarChartProps = {
  items: DashboardProductScore[];
};

export function ScoreRankingBarChart({ items }: ScoreRankingBarChartProps) {
  const option = useMemo(() => {
    const chartItems = items.map((item) => ({
      label: `${item.country} · ${item.product_name_en || item.product_name_cn}`,
      value: toNumber(item.total_score),
      country: item.country,
      productName: item.product_name_en || item.product_name_cn,
    }));
    return buildScoreRankingOption(chartItems);
  }, [items]);

  return <BaseEChart option={option} />;
}

function toNumber(value: string | number | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
