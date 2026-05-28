import type { EChartsOption } from "echarts";

const axisLabelColor = "#64748b";
const gridBorderColor = "#e2e8f0";
const river = "#176B87";
const jade = "#1B8A5A";
const wheat = "#F4B860";

export type ScoreRankingDatum = {
  label: string;
  value: number;
  country: string;
  productName: string;
};

export type CountryScoreDatum = {
  country: string;
  averageScore: number;
  topScore: number;
  recommendationCount: number;
};

export type PriceRangeDatum = {
  label: string;
  min: number;
  median: number;
  avg: number;
  max: number;
  currency: string;
};

export function buildScoreRankingOption(items: ScoreRankingDatum[]): EChartsOption {
  const sorted = [...items].sort((left, right) => left.value - right.value);
  return {
    color: [river],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value) => `${Number(value).toFixed(1)} 分`,
    },
    grid: { left: 16, right: 24, top: 16, bottom: 12, containLabel: true },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { color: axisLabelColor },
      splitLine: { lineStyle: { color: gridBorderColor } },
    },
    yAxis: {
      type: "category",
      data: sorted.map((item) => item.label),
      axisLabel: { color: axisLabelColor, width: 160, overflow: "truncate" },
      axisTick: { show: false },
    },
    series: [
      {
        name: "机会评分",
        type: "bar",
        data: sorted.map((item) => item.value),
        barMaxWidth: 22,
        itemStyle: { borderRadius: [0, 6, 6, 0] },
        label: {
          show: true,
          position: "right",
          color: "#172033",
          formatter: "{c}",
        },
      },
    ],
  };
}

export function buildCountryScoreOption(items: CountryScoreDatum[]): EChartsOption {
  return {
    color: [jade, wheat],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value) => `${Number(value).toFixed(1)} 分`,
    },
    legend: {
      bottom: 0,
      textStyle: { color: axisLabelColor },
    },
    grid: { left: 12, right: 18, top: 18, bottom: 42, containLabel: true },
    xAxis: {
      type: "category",
      data: items.map((item) => item.country),
      axisLabel: { color: axisLabelColor },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { color: axisLabelColor },
      splitLine: { lineStyle: { color: gridBorderColor } },
    },
    series: [
      {
        name: "平均分",
        type: "bar",
        data: items.map((item) => item.averageScore),
        barMaxWidth: 24,
        itemStyle: { borderRadius: [6, 6, 0, 0] },
      },
      {
        name: "最高分",
        type: "line",
        data: items.map((item) => item.topScore),
        symbolSize: 8,
        smooth: true,
      },
    ],
  };
}

export function buildPriceRangeOption(items: PriceRangeDatum[]): EChartsOption {
  return {
    color: [river, jade, wheat],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params) => {
        const values = Array.isArray(params) ? params : [params];
        const title = String(values[0]?.name ?? "");
        const lines = values
          .map((item) => {
            const value = Number(item.value);
            const axisName = String(item.name ?? title);
            const currency = items.find((range) => range.label === axisName)?.currency ?? "";
            return `${item.marker}${item.seriesName}: ${currency} ${value.toFixed(2)}`;
          })
          .join("<br/>");
        return `${title}<br/>${lines}`;
      },
    },
    legend: {
      bottom: 0,
      textStyle: { color: axisLabelColor },
    },
    grid: { left: 16, right: 18, top: 16, bottom: 44, containLabel: true },
    xAxis: {
      type: "category",
      data: items.map((item) => item.label),
      axisLabel: { color: axisLabelColor, width: 120, overflow: "truncate" },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: axisLabelColor },
      splitLine: { lineStyle: { color: gridBorderColor } },
    },
    series: [
      {
        name: "最低价",
        type: "bar",
        data: items.map((item) => item.min),
        barMaxWidth: 18,
        itemStyle: { borderRadius: [5, 5, 0, 0] },
      },
      {
        name: "中位价",
        type: "bar",
        data: items.map((item) => item.median),
        barMaxWidth: 18,
        itemStyle: { borderRadius: [5, 5, 0, 0] },
      },
      {
        name: "最高价",
        type: "bar",
        data: items.map((item) => item.max),
        barMaxWidth: 18,
        itemStyle: { borderRadius: [5, 5, 0, 0] },
      },
    ],
  };
}
