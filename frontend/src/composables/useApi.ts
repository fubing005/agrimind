/**
 * AgriMind API 组合式函数
 *
 * 仅保留 SSE 流式聊天功能（SDK 未自动生成的部分），
 * 其余 REST API 调用由 stores/chat.ts 直接使用 SDK。
 */
import { createSseClient } from "@/client/core/serverSentEvents.gen";
import type { StreamEvent } from "@/client/core/serverSentEvents.gen";
import type { ChatRequest } from "@/client/types.gen";

/** SSE 流式回调集合 */
export interface ChatStreamHandlers {
  onMessage: (chunk: string) => void;
  onSources?: (sources: string[]) => void;
  onDone?: (data: { conversation_id: string; skill_used?: string | null }) => void;
  onBlocked?: (message: string) => void;
  onError?: (error: string) => void;
}

/**
 * 发送 SSE 流式聊天请求，返回 AbortController 用于取消。
 */
export function sendChatStream(
  params: ChatRequest,
  handlers: ChatStreamHandlers,
): AbortController {
  const controller = new AbortController();
  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";

  const { stream } = createSseClient<string>({
    url: `${baseUrl}/api/v1/chat/chat/stream`,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    serializedBody: JSON.stringify(params),
    signal: controller.signal,
    onSseEvent: (event: StreamEvent<unknown>) => {
      dispatchSseEvent(event, handlers);
    },
    onSseError: (error: unknown) => {
      if (error instanceof Error && error.name === "AbortError") return;
      handlers.onError?.(getErrorMessage(error) || "网络请求异常");
    },
  });

  void (async () => {
    try {
      for await (const _chunk of stream) void _chunk;
    } catch {
      // 已被 onSseError 捕获
    }
  })();

  return controller;
}

// ---------------------------------------------------------------------------
// 内部工具
// ---------------------------------------------------------------------------

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "未知错误";
}

function dispatchSseEvent(
  event: StreamEvent<unknown>,
  handlers: ChatStreamHandlers,
): void {
  const eventType = event.event ?? "";
  const raw = event.data;

  switch (eventType) {
    case "message":
      handlers.onMessage(typeof raw === "string" ? raw : String(raw));
      break;
    case "sources":
      try {
        const sources: string[] =
          typeof raw === "string"
            ? (JSON.parse(raw) as string[])
            : Array.isArray(raw)
              ? (raw as string[])
              : [];
        handlers.onSources?.(sources);
      } catch { /* 解析失败忽略 */ }
      break;
    case "done":
      try {
        const done =
          typeof raw === "string"
            ? (JSON.parse(raw) as {
                conversation_id: string;
                skill_used?: string | null;
              })
            : (raw as { conversation_id: string; skill_used?: string | null });
        handlers.onDone?.(done);
      } catch {
        handlers.onDone?.({ conversation_id: "" });
      }
      break;
    case "blocked":
      handlers.onBlocked?.(typeof raw === "string" ? raw : String(raw));
      break;
    case "error":
      handlers.onError?.(typeof raw === "string" ? raw : String(raw));
      break;
  }
}