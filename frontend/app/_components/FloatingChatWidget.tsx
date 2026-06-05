"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { ApiError, ChatMessage, ChatSession, createChatSession, sendChatMessage } from "../_lib/api-client";
import {
  ChatAssistantRole,
  buildChatPageContext,
  chatAssistantRoles,
  chatSessionTitle,
  deriveSafeChatRouteContext,
  roleById,
} from "../_lib/chat-context";
import { useI18n } from "./LanguageProvider";

type FloatingChatWidgetProps = {
  onOpenChange?: (open: boolean) => void;
};

type WidgetMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type FailedRequest = {
  content: string;
};

const quickPrompts = [
  {
    zh: "解释这份报告",
    en: "Explain this report",
  },
  {
    zh: "帮我修改报告",
    en: "Help me revise the report",
  },
  {
    zh: "为什么推荐这些国家",
    en: "Why were these countries recommended?",
  },
  {
    zh: "给我答辩话术",
    en: "Give me defense talking points",
  },
];

const initialRole: ChatAssistantRole = "general_assistant";

export function FloatingChatWidget({ onOpenChange }: FloatingChatWidgetProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { locale, text } = useI18n();
  const [open, setOpen] = useState(false);
  const [roleId, setRoleId] = useState<ChatAssistantRole>(initialRole);
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<WidgetMessage[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failedRequest, setFailedRequest] = useState<FailedRequest | null>(null);
  const launcherRef = useRef<HTMLButtonElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const role = roleById(roleId);
  const routeContext = useMemo(
    () => deriveSafeChatRouteContext(pathname, searchParams),
    [pathname, searchParams],
  );
  const routeContextKey = useMemo(() => JSON.stringify(routeContext.contextIds), [routeContext.contextIds]);
  const pageContext = useMemo(
    () => buildChatPageContext(routeContext, locale, role),
    [locale, role, routeContext],
  );
  const contextSummary = useMemo(() => summarizeContext(routeContext.contextIds, text), [routeContext.contextIds, text]);

  useEffect(() => {
    onOpenChange?.(open);
  }, [onOpenChange, open]);

  useEffect(() => {
    abortRef.current?.abort();
    setSession(null);
    setMessages([]);
    setInput("");
    setError(null);
    setFailedRequest(null);
    setThinking(false);
  }, [routeContextKey, routeContext.page]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closePanel();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const canSubmit = input.trim().length > 0 && !thinking;

  function openPanel() {
    setOpen(true);
  }

  function closePanel() {
    setOpen(false);
    window.setTimeout(() => launcherRef.current?.focus(), 0);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitMessage(input, { appendUser: true });
  }

  async function handleQuickPrompt(prompt: string) {
    await submitMessage(prompt, { appendUser: true });
  }

  async function handleRetry() {
    if (!failedRequest || thinking) {
      return;
    }
    await submitMessage(failedRequest.content, { appendUser: false });
  }

  async function submitMessage(contentValue: string, options: { appendUser: boolean }) {
    const content = contentValue.trim();
    if (!content || thinking) {
      return;
    }

    setOpen(true);
    setThinking(true);
    setError(null);
    setFailedRequest(null);
    if (options.appendUser) {
      setMessages((current) => [...current, { id: createMessageId(), role: "user", content }]);
      setInput("");
    }

    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;

    try {
      const activeSession = session ?? (await createSession(controller.signal));
      const response = await sendChatMessage(
        activeSession.id,
        {
          role: "user",
          content,
          current_page: routeContext.currentPage,
          page_context: pageContext,
          ...routeContext.contextIds,
        },
        controller.signal,
      );
      setSession(response.session);
      setMessages((current) => [
        ...current,
        {
          id: createMessageId(response.assistant_message),
          role: "assistant",
          content: response.assistant_message.content,
        },
      ]);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") {
        return;
      }
      setError(safeChatError(requestError, locale));
      setFailedRequest({ content });
    } finally {
      setThinking(false);
    }
  }

  async function createSession(signal: AbortSignal): Promise<ChatSession> {
    const created = await createChatSession(
      {
        title: chatSessionTitle(routeContext),
        current_page: routeContext.currentPage,
        page_context: pageContext,
        ...routeContext.contextIds,
      },
      signal,
    );
    setSession(created);
    return created;
  }

  return (
    <>
      {!open ? (
        <button
          ref={launcherRef}
          aria-expanded={open}
          aria-label={text("打开全局助手", "Open global assistant")}
          className="fixed bottom-5 right-5 z-40 inline-flex h-14 w-14 items-center justify-center rounded-full bg-river text-white shadow-panel outline-none transition hover:bg-ink focus:ring-4 focus:ring-river/25"
          type="button"
          onClick={openPanel}
        >
          <AssistantIcon />
        </button>
      ) : null}

      {open ? (
        <section
          aria-label={text("全局助手", "Global assistant")}
          className="fixed inset-x-3 bottom-3 top-20 z-40 flex min-h-0 flex-col rounded-lg border border-slate-200 bg-white shadow-panel outline-none lg:inset-x-auto lg:bottom-6 lg:right-4 lg:top-24 lg:w-[26rem]"
          role="dialog"
        >
          <header className="shrink-0 border-b border-slate-200 px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{text("全局助手", "Global Assistant")}</p>
                <p className="mt-1 truncate text-xs text-slate-500">
                  {contextSummary || text("已带入当前页面上下文", "Current page context attached")}
                </p>
              </div>
              <button
                aria-label={text("关闭助手", "Close assistant")}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-ink focus:outline-none focus:ring-2 focus:ring-river/25"
                type="button"
                onClick={closePanel}
              >
                <CloseIcon />
              </button>
            </div>
            <div className="mt-3 flex gap-1 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-1">
              {chatAssistantRoles.map((item) => {
                const active = item.id === roleId;
                return (
                  <button
                    key={item.id}
                    aria-pressed={active}
                    className={`shrink-0 rounded-md px-2.5 py-1.5 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-river/25 ${
                      active ? "bg-river text-white shadow-sm" : "text-slate-600 hover:bg-white hover:text-ink"
                    }`}
                    type="button"
                    onClick={() => setRoleId(item.id)}
                  >
                    {text(item.shortZh, item.shortEn)}
                  </button>
                );
              })}
            </div>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            {messages.length === 0 ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-ink">
                  {text("可以直接问当前页面", "Ask about this page")}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {text(
                    "助手会按当前页面、角色和已识别的报告/分析/产品上下文回答，适合解释、复核和准备答辩。",
                    "The assistant uses the current page, role, and detected report, analysis, or product context for explanations, review, and presentation prep.",
                  )}
                </p>
              </div>
            ) : (
              <div className="grid gap-3">
                {messages.map((message) => (
                  <article
                    key={message.id}
                    className={`max-w-[92%] rounded-lg border px-3 py-2.5 ${
                      message.role === "user"
                        ? "ml-auto border-river/20 bg-river/5"
                        : "mr-auto border-slate-200 bg-slate-50"
                    }`}
                  >
                    <p className="text-xs font-semibold text-slate-500">
                      {message.role === "user" ? text("你", "You") : text(role.labelZh, role.labelEn)}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{message.content}</p>
                  </article>
                ))}
              </div>
            )}

            {thinking ? (
              <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2.5" role="status" aria-live="polite">
                <p className="text-sm font-semibold text-ink">{text("AI 正在思考", "AI is thinking")}</p>
                <div className="mt-3 grid gap-2" aria-hidden="true">
                  <span className="h-2.5 w-full animate-pulse rounded bg-slate-100" />
                  <span className="h-2.5 w-2/3 animate-pulse rounded bg-slate-100" />
                </div>
              </div>
            ) : null}

            {error ? (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3" role="alert">
                <p className="text-sm font-semibold text-red-800">{text("聊天暂不可用", "Chat unavailable")}</p>
                <p className="mt-1 text-sm leading-6 text-red-700">{error}</p>
                {failedRequest ? (
                  <button
                    className="mt-3 rounded-md bg-red-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300"
                    disabled={thinking}
                    type="button"
                    onClick={() => void handleRetry()}
                  >
                    {text("重试", "Retry")}
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="shrink-0 border-t border-slate-200 p-4">
            <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
              {quickPrompts.map((prompt) => {
                const label = text(prompt.zh, prompt.en);
                return (
                  <button
                    key={prompt.zh}
                    className="shrink-0 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-river/30 hover:bg-river/5 hover:text-ink focus:outline-none focus:ring-2 focus:ring-river/25"
                    disabled={thinking}
                    type="button"
                    onClick={() => void handleQuickPrompt(label)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <form className="grid gap-2" onSubmit={(event) => void handleSubmit(event)}>
              <label className="sr-only" htmlFor="global-chat-input">
                {text("输入问题", "Message")}
              </label>
              <textarea
                id="global-chat-input"
                className="max-h-32 min-h-20 resize-y rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                placeholder={text("问问当前报告、看板或产品...", "Ask about the current report, dashboard, or product...")}
                value={input}
                onChange={(event) => setInput(event.target.value)}
              />
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs leading-5 text-slate-500">
                  {text("不要输入密钥或客户隐私。", "Do not enter secrets or private customer data.")}
                </p>
                <button
                  className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={!canSubmit}
                  type="submit"
                >
                  {thinking ? text("发送中", "Sending") : text("发送", "Send")}
                </button>
              </div>
            </form>
          </div>
        </section>
      ) : null}
    </>
  );
}

function summarizeContext(
  contextIds: {
    report_id?: number;
    analysis_id?: number;
    product_id?: number;
    company_id?: number;
  },
  text: (zh: string, en?: string) => string,
): string {
  const parts: string[] = [];
  if (contextIds.report_id) {
    parts.push(text(`报告 #${contextIds.report_id}`, `Report #${contextIds.report_id}`));
  }
  if (contextIds.analysis_id) {
    parts.push(text(`分析 #${contextIds.analysis_id}`, `Analysis #${contextIds.analysis_id}`));
  }
  if (contextIds.product_id) {
    parts.push(text(`产品 #${contextIds.product_id}`, `Product #${contextIds.product_id}`));
  }
  if (contextIds.company_id) {
    parts.push(text(`企业 #${contextIds.company_id}`, `Company #${contextIds.company_id}`));
  }
  return parts.length > 0 ? parts.join(" · ") : "";
}

function safeChatError(error: unknown, locale: "zh-CN" | "en"): string {
  if (error instanceof ApiError && error.status === 422) {
    return locale === "en"
      ? "The current page context cannot be used for chat. Open a valid report, dashboard, or product and try again."
      : "当前页面上下文暂不能用于聊天，请打开有效报告、看板或产品后重试。";
  }
  if (error instanceof ApiError && error.status === 404) {
    return locale === "en"
      ? "The current report, analysis, or product was not found. Refresh the page and try again."
      : "当前报告、分析或产品不存在，请刷新页面后重试。";
  }
  return locale === "en"
    ? "The assistant could not respond just now. Please try again."
    : "助手刚才未能完成回答，请稍后重试。";
}

function createMessageId(message?: ChatMessage): string {
  if (message) {
    return `${message.session_id}-${message.id}`;
  }
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function AssistantIcon() {
  return (
    <svg aria-hidden="true" className="h-6 w-6" fill="none" viewBox="0 0 24 24">
      <path
        d="M5 9.5C5 6.5 7.5 4 10.5 4h3C16.5 4 19 6.5 19 9.5v2.8c0 3-2.5 5.5-5.5 5.5h-1.2l-3.8 2.4v-2.4C6.5 17.8 5 15.3 5 12.3V9.5Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path d="M9 10.5h6M9 13.5h3.8" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
      <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
    </svg>
  );
}
