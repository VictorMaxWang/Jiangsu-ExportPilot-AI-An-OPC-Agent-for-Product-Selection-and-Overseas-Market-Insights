import type { ReactNode } from "react";

type SuccessStateProps = {
  title: string;
  description?: string;
  action?: ReactNode;
};

export function SuccessState({ title, description, action }: SuccessStateProps) {
  return (
    <div className="rounded-lg border border-jade/30 bg-jade/10 p-5 shadow-sm" role="status" aria-live="polite">
      <h3 className="text-base font-semibold text-jade">{title}</h3>
      {description ? <p className="mt-2 text-sm leading-6 text-slate-700">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
