"use client";

import { FormEvent, useMemo, useState } from "react";
import { EmptyState } from "../_components/EmptyState";
import { ErrorState } from "../_components/ErrorState";
import { FallbackNotice } from "../_components/FallbackNotice";
import { LoadingState } from "../_components/LoadingState";
import { PageHeader } from "../_components/PageHeader";
import { SuccessState } from "../_components/SuccessState";
import { useI18n } from "../_components/LanguageProvider";
import { AiChatMessage, chatWithAi, getFriendlyErrorMessage } from "../_lib/api-client";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  model?: string | null;
};

const starterPrompts = [
  {
    zh: "请帮我解释最近一次出海分析报告中，为什么美国市场优先级更高。",
    en: "Explain why the US market ranks higher in the latest export analysis report.",
  },
  {
    zh: "请给江苏家纺产品生成适合 Etsy 的英文卖点。",
    en: "Generate English Etsy selling points for a Jiangsu home textile product.",
  },
  {
    zh: "请列出正式投放前需要复核的数据来源。",
    en: "List the data sources we should verify before a real launch.",
  },
];

export default function ChatPage() {
  const { text, locale } = useI18n();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastModel, setLastModel] = useState<string | null>(null);

  const canSubmit = input.trim().length > 0 && !submitting;
  const systemMessage = useMemo<AiChatMessage>(
    () => ({
      role: "system",
      content:
        locale === "en"
          ? "You are Jiangsu ExportPilot's export product-selection assistant. Answer concisely. Do not request or reveal API keys, secrets, cookies, or credentials. When data is uncertain, state the caveat."
          : "你是苏品智航的出海选品助手。请简洁回答，不要索取或暴露 API Key、密钥、Cookie、凭据等敏感信息。数据不确定时必须说明边界。",
    }),
    [locale],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = input.trim();
    if (!content || submitting) {
      return;
    }

    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content,
    };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput("");
    setSubmitting(true);
    setError(null);

    try {
      const response = await chatWithAi({
        messages: [
          systemMessage,
          ...nextMessages.slice(-8).map((message): AiChatMessage => ({
            role: message.role,
            content: message.content,
          })),
        ],
        temperature: 0.4,
        max_tokens: 1200,
        json_mode: false,
      });
      setLastModel(response.model);
      setMessages((current) => [
        ...current,
        {
          id: createMessageId(),
          role: "assistant",
          content: response.content,
          model: response.model,
        },
      ]);
    } catch (requestError) {
      setError(safeChatError(getFriendlyErrorMessage(requestError), locale));
    } finally {
      setSubmitting(false);
    }
  }

  function applyStarterPrompt(prompt: string) {
    setInput(prompt);
    setError(null);
  }

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <PageHeader
          eyebrow="AI 助手"
          eyebrowEn="AI Assistant"
          title="出海聊天"
          titleEn="Export Chat"
          description="围绕产品草稿、市场分析、看板、营销文案和报告内容进行问答；前端只调用后端代理接口，不接触第三方密钥。"
          descriptionEn="Ask about product drafts, market analysis, dashboards, copy, and reports. The frontend only calls the backend proxy and never handles third-party secrets."
        />
        <div className="rounded-lg border border-river/20 bg-river/5 px-4 py-3 text-sm font-semibold text-river">
          {lastModel ? text(`模型：${lastModel}`, `Model: ${lastModel}`) : text("后端 Qwen 通道", "Backend Qwen channel")}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.72fr_0.28fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel sm:p-5">
          <div className="min-h-[24rem]">
            {messages.length === 0 ? (
              <EmptyState
                title={text("还没有对话", "No conversation yet")}
                description={text(
                  "可以询问产品草稿、目标国家、报告证据边界或营销文案方向。",
                  "Ask about product drafts, target countries, report evidence boundaries, or copy direction.",
                )}
              />
            ) : (
              <div className="grid gap-3">
                {messages.map((message) => (
                  <article
                    key={message.id}
                    className={`max-w-[min(100%,48rem)] rounded-lg border p-4 ${
                      message.role === "user"
                        ? "ml-auto border-river/20 bg-river/5"
                        : "mr-auto border-slate-200 bg-slate-50"
                    }`}
                  >
                    <p className="text-xs font-semibold text-slate-500">
                      {message.role === "user" ? text("你", "You") : text("苏品智航助手", "ExportPilot Assistant")}
                      {message.model ? ` · ${message.model}` : ""}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{message.content}</p>
                  </article>
                ))}
              </div>
            )}
            {submitting ? <div className="mt-4"><LoadingState label={text("正在调用后端 Qwen", "Calling backend Qwen")} rows={2} /></div> : null}
          </div>

          <form className="mt-5 grid gap-3" onSubmit={handleSubmit}>
            <label className="grid gap-2">
              <span className="text-sm font-medium text-slate-700">{text("输入问题", "Message")}</span>
              <textarea
                className="min-h-28 resize-y rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                placeholder={text("例如：请解释这份报告的最大风险。", "For example: explain the biggest risk in this report.")}
                value={input}
                onChange={(event) => setInput(event.target.value)}
              />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs leading-5 text-slate-500">
                {text("不要输入密钥、账号、Cookie、手机号、地址等敏感信息。", "Do not enter keys, accounts, cookies, phone numbers, addresses, or other sensitive data.")}
              </p>
              <button
                className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={!canSubmit}
                type="submit"
              >
                {submitting ? text("发送中", "Sending") : text("发送", "Send")}
              </button>
            </div>
          </form>

          <div className="mt-4 grid gap-3">
            {error ? <ErrorState message={error} /> : null}
            {lastModel ? (
              <SuccessState
                title={text("回答已生成", "Answer generated")}
                description={text("模型响应来自后端代理，前端未接触第三方 API 密钥。", "The model response came through the backend proxy; the frontend did not handle third-party API keys.")}
              />
            ) : null}
          </div>
        </section>

        <aside className="grid content-start gap-4">
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
            <h2 className="text-lg font-semibold text-ink">{text("可问什么", "Suggested prompts")}</h2>
            <div className="mt-4 grid gap-2">
              {starterPrompts.map((prompt) => {
                const label = text(prompt.zh, prompt.en);
                return (
                  <button
                    key={prompt.zh}
                    className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm leading-6 text-slate-700 transition hover:border-river/30 hover:bg-river/5 hover:text-ink"
                    type="button"
                    onClick={() => applyStarterPrompt(label)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </section>
          <FallbackNotice
            source="ai"
            title={text("聊天证据边界", "Chat evidence boundary")}
            description={text(
              "聊天回答适合解释和草拟，不会替代正式分析、看板和报告里的结构化来源记录。",
              "Chat answers are useful for explanation and drafting; they do not replace structured source records in analysis, dashboards, and reports.",
            )}
          />
        </aside>
      </div>
    </div>
  );
}

function safeChatError(message: string, locale: "zh-CN" | "en"): string {
  const fallback =
    locale === "en"
      ? "Chat is temporarily unavailable. Check backend AI configuration and try again."
      : "聊天暂不可用，请检查后端 AI 配置后重试。";
  if (!message.trim()) {
    return fallback;
  }
  if (/后端不可用|Failed to fetch|NetworkError|network request failed/i.test(message)) {
    return fallback;
  }
  if (/后端未配置 Bailian|BAILIAN_NOT_CONFIGURED|Bailian is not configured/i.test(message)) {
    return locale === "en"
      ? "Bailian is not configured on the backend. Configure the server environment and try again."
      : "后端未配置 Bailian，请配置服务器环境变量后重试。";
  }
  if (/traceback|stack\s*trace|exception|file\s+".+",\s+line\s+\d+|at\s+\S+\s*\(|\.(py|ts|tsx|js):\d+|[A-Za-z]:\\|\/(?:app|usr|var|home)\/|node_modules|key|token|secret|cookie/i.test(message)) {
    return fallback;
  }
  return message;
}

function createMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
