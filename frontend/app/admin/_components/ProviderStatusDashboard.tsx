"use client";

import { useEffect, useMemo, useState } from "react";

import { ErrorState } from "../../_components/ErrorState";
import { LoadingState } from "../../_components/LoadingState";
import { ProviderStatusBadge } from "../../_components/ProviderStatusBadge";
import {
  ApiError,
  type ProviderId,
  type ProviderStatusItem,
  type ProviderTestResponse,
  getFriendlyErrorMessage,
  listProviderStatuses,
  testProvider,
} from "../../_lib/api-client";

type TestResultMap = Partial<Record<ProviderId, ProviderTestResponse>>;

type ProviderStatusDashboardProps = {
  requireAdminPassword?: boolean;
};

export function ProviderStatusDashboard({ requireAdminPassword = false }: ProviderStatusDashboardProps) {
  const [adminPassword, setAdminPassword] = useState("");
  const [passwordRequired, setPasswordRequired] = useState(requireAdminPassword);
  const [providers, setProviders] = useState<ProviderStatusItem[]>([]);
  const [lastTests, setLastTests] = useState<TestResultMap>({});
  const [loading, setLoading] = useState(!requireAdminPassword);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [testingProvider, setTestingProvider] = useState<ProviderId | null>(null);

  useEffect(() => {
    if (requireAdminPassword) {
      setPasswordRequired(true);
    }
  }, [requireAdminPassword]);

  useEffect(() => {
    if (passwordRequired) {
      setLoading(false);
      return;
    }

    let active = true;
    async function loadInitialStatuses() {
      setLoading(true);
      setErrorMessage(null);
      try {
        const payload = await listProviderStatuses();
        if (active) {
          setProviders(payload.providers);
        }
      } catch (error) {
        if (active) {
          if (error instanceof ApiError && error.status === 401) {
            setPasswordRequired(true);
            setProviders([]);
          }
          setErrorMessage(getFriendlyErrorMessage(error));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadInitialStatuses();
    return () => {
      active = false;
    };
  }, [passwordRequired]);

  async function loadStatuses() {
    if (passwordRequired && !adminPassword.trim()) {
      setErrorMessage("请输入管理员密码后加载状态。");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const payload = await listProviderStatuses({ adminPassword });
      setProviders(payload.providers);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setPasswordRequired(true);
        setProviders([]);
      }
      setErrorMessage(getFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function runProviderTest(provider: ProviderId) {
    if (passwordRequired && !adminPassword.trim()) {
      setErrorMessage("请输入管理员密码后执行测试。");
      return;
    }

    setTestingProvider(provider);
    setErrorMessage(null);
    try {
      const result = await testProvider(provider, { adminPassword });
      setLastTests((current) => ({ ...current, [provider]: result }));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setErrorMessage("管理员密码无效或缺失，未执行测试。");
        return;
      }
      setLastTests((current) => ({
        ...current,
        [provider]: {
          provider,
          status: "unavailable",
          checked_at: new Date().toISOString(),
          latency_ms: 0,
          fallback_used: false,
          message: "后端状态测试失败。",
          sample_count: 0,
          error_code: "FRONTEND_TEST_REQUEST_FAILED",
          configured: false,
          live_ping_success: null,
          live_search_success: null,
          fallback_available: false,
          cache_bypassed: false,
          auth_mode: null,
        },
      }));
    } finally {
      setTestingProvider(null);
    }
  }

  const priorityCounts = useMemo(() => {
    return providers.reduce<Record<string, number>>((counts, provider) => {
      counts[provider.mvp_priority] = (counts[provider.mvp_priority] ?? 0) + 1;
      return counts;
    }, {});
  }, [providers]);

  const passwordPanel = (
    <AdminPasswordPanel
      adminPassword={adminPassword}
      requireAdminPassword={passwordRequired}
      onAdminPasswordChange={setAdminPassword}
      onLoad={() => void loadStatuses()}
    />
  );

  if (loading) {
    return (
      <div className="grid gap-5">
        {passwordPanel}
        <LoadingState label="正在加载数据源能力状态" rows={6} />
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="grid gap-5">
        {passwordPanel}
        <ErrorState
          title="数据源状态暂不可用"
          message={errorMessage}
          retryAction={
            <button
              type="button"
              onClick={() => void loadStatuses()}
              className="rounded-md bg-red-700 px-3 py-2 text-sm font-semibold text-white hover:bg-red-800"
            >
              重新加载
            </button>
          }
        />
      </div>
    );
  }

  if (passwordRequired && providers.length === 0) {
    return <div className="grid gap-5">{passwordPanel}</div>;
  }

  return (
    <div className="grid gap-5">
      {passwordPanel}
      <div className="grid gap-3 sm:grid-cols-3">
        {(["P0", "P1", "P2"] as const).map((priority) => (
          <div key={priority} className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{priority}</p>
            <p className="mt-2 text-2xl font-semibold text-ink">{priorityCounts[priority] ?? 0}</p>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-semibold">数据源</th>
                <th className="px-4 py-3 font-semibold">优先级</th>
                <th className="px-4 py-3 font-semibold">状态</th>
                <th className="px-4 py-3 font-semibold">默认启用</th>
                <th className="px-4 py-3 font-semibold">兜底文件</th>
                <th className="px-4 py-3 font-semibold">测试</th>
                <th className="px-4 py-3 font-semibold">最近测试结果</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {providers.map((provider) => (
                <tr key={provider.provider} className="align-top">
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink">{provider.display_name}</div>
                    <div className="mt-1 text-xs leading-5 text-slate-500">{provider.notes}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{provider.mvp_priority}</td>
                  <td className="px-4 py-3">
                    <ProviderStatusBadge status={provider.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-700">{provider.default_enabled ? "是" : "否"}</td>
                  <td className="px-4 py-3 text-slate-600">{provider.fallback ?? "-"}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => void runProviderTest(provider.provider)}
                      disabled={testingProvider === provider.provider}
                      className="rounded-md bg-ink px-3 py-2 text-xs font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      {testingProvider === provider.provider ? "测试中" : "测试"}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <LastTestResult result={lastTests[provider.provider]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function AdminPasswordPanel({
  adminPassword,
  requireAdminPassword,
  onAdminPasswordChange,
  onLoad,
}: {
  adminPassword: string;
  requireAdminPassword: boolean;
  onAdminPasswordChange: (value: string) => void;
  onLoad: () => void;
}) {
  if (!requireAdminPassword) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-600">
        这里只显示配置状态，不显示密钥。
      </div>
    );
  }

  return (
    <div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4">
      <div>
        <p className="text-sm font-semibold text-ink">管理员密码</p>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          这里只显示配置状态，不显示密钥。密码仅保存在当前页面会话状态中，刷新后会清空。
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          type="password"
          value={adminPassword}
          onChange={(event) => onAdminPasswordChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onLoad();
            }
          }}
          className="min-h-10 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-ink outline-none transition focus:border-ink focus:ring-2 focus:ring-slate-200"
          placeholder="输入管理员密码"
          autoComplete="current-password"
        />
        <button
          type="button"
          onClick={onLoad}
          className="min-h-10 rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
        >
          加载状态
        </button>
      </div>
    </div>
  );
}

function LastTestResult({ result }: { result: ProviderTestResponse | undefined }) {
  if (!result) {
    return <span className="text-slate-500">未测试</span>;
  }

  return (
    <div className="grid gap-2">
      <ProviderStatusBadge status={result.status} />
      <p className="text-xs leading-5 text-slate-600">{result.message}</p>
      <p className="text-xs text-slate-500">
        {formatDateTime(result.checked_at)} · {result.latency_ms}ms · 样本 {result.sample_count}
      </p>
    </div>
  );
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
