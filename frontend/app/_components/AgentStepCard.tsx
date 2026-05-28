export type AgentStepStatus = "pending" | "running" | "complete" | "warning" | "error";

type AgentStepCardProps = {
  title: string;
  description: string;
  status: AgentStepStatus;
  stepNumber?: number;
  meta?: string;
};

const statusLabels: Record<AgentStepStatus, string> = {
  pending: "待处理",
  running: "演示中",
  complete: "已覆盖",
  warning: "需兜底",
  error: "需检查",
};

const statusClassNames: Record<AgentStepStatus, string> = {
  pending: "bg-slate-100 text-slate-600 ring-slate-200",
  running: "bg-river/10 text-river ring-river/20",
  complete: "bg-jade/10 text-jade ring-jade/20",
  warning: "bg-wheat/15 text-ink ring-wheat/30",
  error: "bg-red-50 text-red-700 ring-red-200",
};

export function AgentStepCard({
  title,
  description,
  status,
  stepNumber,
  meta,
}: AgentStepCardProps) {
  return (
    <article className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {typeof stepNumber === "number" ? (
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-river/10 text-sm font-semibold text-river ring-1 ring-river/20">
              {stepNumber}
            </span>
          ) : null}
          <h3 className="text-base font-semibold text-ink">{title}</h3>
        </div>
        <span
          className={`inline-flex shrink-0 rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${statusClassNames[status]}`}
        >
          {statusLabels[status]}
        </span>
      </div>
      <p className="text-sm leading-6 text-slate-600">{description}</p>
      {meta ? <p className="text-xs font-medium text-slate-500">{meta}</p> : null}
    </article>
  );
}
