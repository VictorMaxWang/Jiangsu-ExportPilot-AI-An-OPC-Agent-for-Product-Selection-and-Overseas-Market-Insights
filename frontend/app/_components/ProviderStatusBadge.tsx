export type ProviderStatus =
  | "integrated"
  | "public"
  | "configured"
  | "backend_only"
  | "optional"
  | "fallback"
  | "sample"
  | "future"
  | "not_default"
  | "active_no_key"
  | "not_configured"
  | "optional_no_key_first"
  | "pending_manual_registration"
  | "fallback_only"
  | "disabled"
  | "unavailable"
  | "success"
  | "pending";

type ProviderStatusBadgeProps = {
  status: ProviderStatus;
  label?: string;
};

const statusLabels: Record<ProviderStatus, string> = {
  integrated: "已接入",
  public: "公开 API",
  configured: "已配置",
  backend_only: "后端读取",
  optional: "可选",
  fallback: "兜底可用",
  sample: "样本兜底",
  future: "后续扩展",
  not_default: "未默认启用",
  active_no_key: "公开可用",
  not_configured: "未配置",
  optional_no_key_first: "免配置优先",
  pending_manual_registration: "待注册",
  fallback_only: "仅兜底",
  disabled: "已禁用",
  unavailable: "不可用",
  success: "测试通过",
  pending: "等待配置",
};

const statusClassNames: Record<ProviderStatus, string> = {
  integrated: "bg-jade/10 text-jade ring-jade/20",
  public: "bg-river/10 text-river ring-river/20",
  configured: "bg-jade/10 text-jade ring-jade/20",
  backend_only: "bg-slate-100 text-slate-700 ring-slate-200",
  optional: "bg-wheat/15 text-ink ring-wheat/30",
  fallback: "bg-wheat/15 text-ink ring-wheat/30",
  sample: "bg-slate-100 text-slate-700 ring-slate-200",
  future: "bg-slate-100 text-slate-500 ring-slate-200",
  not_default: "bg-slate-100 text-slate-600 ring-slate-200",
  active_no_key: "bg-river/10 text-river ring-river/20",
  not_configured: "bg-slate-100 text-slate-600 ring-slate-200",
  optional_no_key_first: "bg-wheat/15 text-ink ring-wheat/30",
  pending_manual_registration: "bg-slate-100 text-slate-600 ring-slate-200",
  fallback_only: "bg-wheat/15 text-ink ring-wheat/30",
  disabled: "bg-slate-100 text-slate-500 ring-slate-200",
  unavailable: "bg-red-50 text-red-700 ring-red-200",
  success: "bg-jade/10 text-jade ring-jade/20",
  pending: "bg-slate-100 text-slate-600 ring-slate-200",
};

export function ProviderStatusBadge({ status, label }: ProviderStatusBadgeProps) {
  return (
    <span
      className={`inline-flex w-fit items-center rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${statusClassNames[status]}`}
    >
      {label ?? statusLabels[status]}
    </span>
  );
}
