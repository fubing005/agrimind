/**
 * AgriMind chat store (Pinia)
 *
 * - 后端是会话与消息的唯一真相源，本地不作缓存
 * - 所有更新走不可变路径（spread / concat）
 * - SSE 流式期间仅更新前端状态，持久化由后端在流式端点内完成
 */
import { defineStore } from "pinia";
import { ref } from "vue";

import {
  createConversationApiV1SessionsPost,
  deleteConversationApiV1SessionsConversationIdDelete,
  getConversationApiV1SessionsConversationIdGet,
  listConversationsApiV1SessionsGet,
  updateConversationApiV1SessionsConversationIdPatch,
} from "@/client/sdk.gen";
import type {
  ConversationSummary,
  MessageItem,
} from "@/client/types.gen";

/** UI 侧消息 */
export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  sources?: string[];
  skillUsed?: string;
  blocked?: boolean;
}

/** UI 侧会话 */
export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

function toChatMessage(msg: MessageItem): ChatMessage {
  return {
    role: msg.role,
    content: msg.content,
    timestamp: msg.timestamp ? new Date(msg.timestamp).getTime() : Date.now(),
    sources: msg.sources ?? undefined,
    skillUsed: msg.skill_used ?? undefined,
  };
}

async function unwrap<T>(p: Promise<{ data: T; response: Response }>): Promise<T> {
  const { data, response } = await p;
  if (!response.ok) {
    throw new Error(`请求失败 (HTTP ${response.status})`);
  }
  return data;
}

export const useChatStore = defineStore("chat", () => {
  const activeConversationId = ref<string>("");
  const conversations = ref<Conversation[]>([]);
  const isLoading = ref<boolean>(false);
  const isLoaded = ref<boolean>(false);
  const error = ref<string | null>(null);

  function getActiveConversation(): Conversation | undefined {
    if (!activeConversationId.value) return undefined;
    return conversations.value.find((c) => c.id === activeConversationId.value);
  }

  function replaceConversation(updated: Conversation): void {
    conversations.value = conversations.value.map((c) =>
      c.id === updated.id ? updated : c,
    );
  }

  /** 从后端拉取会话列表 */
  async function loadConversationsFromBackend(): Promise<void> {
    isLoading.value = true;
    error.value = null;
    try {
      const data = await unwrap(
        listConversationsApiV1SessionsGet({ throwOnError: true }),
      );
      const summaries = data ?? [];
      conversations.value = summaries.map((s: ConversationSummary) => ({
        id: s.id,
        title: s.title,
        messages: [],
        createdAt: s.created_at,
        updatedAt: s.updated_at,
      }));
      if (
        activeConversationId.value &&
        !summaries.some((s) => s.id === activeConversationId.value)
      ) {
        activeConversationId.value = summaries[0]?.id ?? "";
      } else if (!activeConversationId.value) {
        activeConversationId.value = summaries[0]?.id ?? "";
      }
      isLoaded.value = true;
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "加载会话失败";
      isLoaded.value = true;
    } finally {
      isLoading.value = false;
    }
  }

  /** 创建新会话 */
  async function createConversation(): Promise<Conversation> {
    error.value = null;
    try {
      const summary = await unwrap(
        createConversationApiV1SessionsPost({
          body: { title: "新对话", conversation_id: null },
          throwOnError: true,
        }),
      );
      const conv: Conversation = {
        id: summary.id,
        title: summary.title,
        messages: [],
        createdAt: summary.created_at,
        updatedAt: summary.updated_at,
      };
      conversations.value = [conv, ...conversations.value];
      activeConversationId.value = conv.id;
      return conv;
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "创建会话失败";
      throw e;
    }
  }

  /** 切换活跃会话 */
  async function switchConversation(id: string): Promise<void> {
    activeConversationId.value = id;
    const conv = getActiveConversation();
    if (!conv) return;
    if (conv.messages.length > 0) return;
    try {
      const detail = await unwrap(
        getConversationApiV1SessionsConversationIdGet({
          path: { conversation_id: id },
          throwOnError: true,
        }),
      );
      replaceConversation({
        id: detail.id,
        title: detail.title,
        messages: (detail.messages ?? []).map(toChatMessage),
        createdAt: detail.created_at,
        updatedAt: detail.updated_at,
      });
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "加载会话详情失败";
    }
  }

  /** 删除会话 */
  async function deleteConversation(id: string): Promise<void> {
    const snapshot = conversations.value;
    const wasActive = activeConversationId.value === id;
    try {
      await unwrap(
        deleteConversationApiV1SessionsConversationIdDelete({
          path: { conversation_id: id },
          throwOnError: true,
        }),
      );
      conversations.value = snapshot.filter((c) => c.id !== id);
      if (wasActive) {
        activeConversationId.value = conversations.value[0]?.id ?? "";
      }
    } catch (e: unknown) {
      conversations.value = snapshot;
      error.value = e instanceof Error ? e.message : "删除会话失败";
      throw e;
    }
  }

  /** 修改会话标题 */
  async function renameConversation(id: string, title: string): Promise<void> {
    const conv = conversations.value.find((c) => c.id === id);
    if (!conv) return;
    const prevTitle = conv.title;
    replaceConversation({ ...conv, title });
    try {
      const detail = await unwrap(
        updateConversationApiV1SessionsConversationIdPatch({
          path: { conversation_id: id },
          body: { title },
          throwOnError: true,
        }),
      );
      replaceConversation({ ...conv, title: detail.title, updatedAt: detail.updated_at });
    } catch (e: unknown) {
      replaceConversation({ ...conv, title: prevTitle });
      error.value = e instanceof Error ? e.message : "更新标题失败";
      throw e;
    }
  }

  /** 追加消息到当前会话（仅前端，后端在流式端点内持久化） */
  function appendMessage(
    message: Omit<ChatMessage, "timestamp">,
  ): Conversation | undefined {
    const conv = getActiveConversation();
    if (!conv) return undefined;
    const chatMsg: ChatMessage = { ...message, timestamp: Date.now() };
    replaceConversation({
      ...conv,
      messages: [...conv.messages, chatMsg],
      updatedAt: new Date().toISOString(),
      title: shouldAutoTitle(conv, chatMsg) ? deriveTitle(chatMsg.content) : conv.title,
    });
    return getActiveConversation();
  }

  /** 追加 assistant 片段（SSE 期间） */
  function appendAssistantChunk(chunk: string): void {
    const conv = getActiveConversation();
    if (!conv) return;
    const msgs = conv.messages;
    const last = msgs[msgs.length - 1];
    if (!last || last.role !== "assistant") return;
    replaceConversation({
      ...conv,
      messages: [...msgs.slice(0, -1), { ...last, content: last.content + chunk }],
      updatedAt: new Date().toISOString(),
    });
  }

  /** 标记最后一条 assistant 消息为 blocked */
  function markLastAssistantBlocked(message: string): void {
    const conv = getActiveConversation();
    if (!conv) return;
    const msgs = conv.messages;
    const last = msgs[msgs.length - 1];
    if (!last || last.role !== "assistant") return;
    replaceConversation({
      ...conv,
      messages: [...msgs.slice(0, -1), { ...last, content: message, blocked: true }],
      updatedAt: new Date().toISOString(),
    });
  }

  /** 设置最后一条 assistant 消息的 sources */
  function setLastAssistantSources(sources: string[]): void {
    const conv = getActiveConversation();
    if (!conv) return;
    const msgs = conv.messages;
    const last = msgs[msgs.length - 1];
    if (!last || last.role !== "assistant") return;
    replaceConversation({
      ...conv,
      messages: [...msgs.slice(0, -1), { ...last, sources }],
      updatedAt: new Date().toISOString(),
    });
  }

  function clearAll(): void {
    conversations.value = [];
    activeConversationId.value = "";
  }

  return {
    activeConversationId,
    conversations,
    isLoading,
    isLoaded,
    error,
    getActiveConversation,
    loadConversationsFromBackend,
    createConversation,
    switchConversation,
    deleteConversation,
    renameConversation,
    appendMessage,
    appendAssistantChunk,
    markLastAssistantBlocked,
    setLastAssistantSources,
    clearAll,
  };
});

// ---------------------------------------------------------------------------
// 内部工具
// ---------------------------------------------------------------------------

function shouldAutoTitle(conv: Conversation, msg: ChatMessage): boolean {
  if (msg.role !== "user") return false;
  if (conv.title && conv.title !== "新对话") return false;
  return !conv.messages.some((m) => m.role === "user");
}

function deriveTitle(content: string): string {
  const trimmed = content.trim();
  if (trimmed.length <= 20) return trimmed || "新对话";
  return trimmed.slice(0, 20) + "...";
}