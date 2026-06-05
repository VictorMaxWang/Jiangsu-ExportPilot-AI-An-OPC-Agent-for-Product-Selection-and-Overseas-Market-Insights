"use client";

import { useMemo } from "react";
import type { DashboardCountryScore } from "../../app/_lib/api-client";
import { BaseEChart } from "./BaseEChart";
import { buildCountryScoreOption } from "./chart-options";

type CountryRecommendationChartProps = {
  items: DashboardCountryScore[];
};

export function CountryRecommendationChart({ items }: CountryRecommendationChartProps) {
  const chartHeight = Math.max(320, items.length * 38 + 88);
  const option = useMemo(() => {
    const chartItems = items.map((item) => ({
      country: item.country,
      averageScore: toNumber(item.average_score),
      topScore: toNumber(item.top_score),
      recommendationCount: item.recommendation_count,
    }));
    return buildCountryScoreOption(chartItems);
  }, [items]);

  return <BaseEChart height={chartHeight} option={option} />;
}

function toNumber(value: string | number | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
