import type { ReactNode } from "react";

type ErrorStateProps = {
  title?: string;
  message: string;
  retryAction?: ReactNode;
};

export function ErrorState({ title = "状态暂不可用", message, retryAction }: ErrorStateProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-5 shadow-sm" role="alert">
      <h3 className="text-base font-semibold text-red-800">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-red-700">{message}</p>
      {retryAction ? <div className="mt-4">{retryAction}</div> : null}
    </div>
  );
}
