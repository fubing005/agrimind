<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onBeforeUnmount } from "vue";
import { useChatStore } from "@/stores/chat";
import { sendChatStream } from "@/composables/useApi";
import ChatBubble from "@/components/ChatBubble.vue";
import ChatInput from "@/components/ChatInput.vue";
import SkillCard from "@/components/SkillCard.vue";
import Sidebar from "@/components/Sidebar.vue";

const chatStore = useChatStore();
const messagesContainer = ref<HTMLElement>();
const abortController = ref<AbortController | null>(null);

onMounted(async () => {
  if (!chatStore.isLoaded) {
    await chatStore.loadConversationsFromBackend();
  }
});

/** 切换会话时取消正在进行的流 */
watch(
  () => chatStore.activeConversationId,
  () => abortController.value?.abort(),
);

/** 组件卸载时也取消，避免 setState on unmounted */
onBeforeUnmount(() => abortController.value?.abort());

/** 自动滚动到底部 */
async function scrollToBottom(): Promise<void> {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}

watch(
  () => chatStore.getActiveConversation()?.messages.length,
  () => scrollToBottom(),
);

/** 发送消息（SSE 流式） */
async function handleSend(message: string): Promise<void> {
  // 确保有活跃会话（先 await 拿到真实 ID，避免临时 ID 提交）
  if (!chatStore.getActiveConversation()) {
    await chatStore.createConversation();
  }
  const conv = chatStore.getActiveConversation();
  if (!conv) return;

  // 追加 user 消息 + 空 assistant 占位
  chatStore.appendMessage({ role: "user", content: message });
  chatStore.appendMessage({ role: "assistant", content: "" });
  chatStore.isLoading = true;

  // 发送 SSE 流式请求
  abortController.value = sendChatStream(
    { message, conversation_id: conv.id },
    {
      onMessage: (chunk) => {
        chatStore.appendAssistantChunk(chunk);
        scrollToBottom();
      },
      onSources: (sources) => {
        chatStore.setLastAssistantSources(sources);
      },
      onDone: () => {
        chatStore.isLoading = false;
        abortController.value = null;
      },
      onBlocked: (blockedMsg) => {
        chatStore.markLastAssistantBlocked(blockedMsg);
        chatStore.isLoading = false;
        abortController.value = null;
      },
      onError: (errorMsg) => {
        // 只把错误追加到现有 assistant 占位，不再 append 新消息
        chatStore.appendAssistantChunk(`\n\n⚠️ 请求出错: ${errorMsg}`);
        chatStore.isLoading = false;
        abortController.value = null;
      },
    },
  );
}

/** 技能卡片选择 */
function handleSkillSelect(prompt: string): void {
  void handleSend(prompt);
}

function getMessages() {
  return chatStore.getActiveConversation()?.messages ?? [];
}

function showWelcome(): boolean {
  return getMessages().length === 0;
}
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <!-- 侧边栏 -->
    <Sidebar />

    <!-- 主内容区 -->
    <main class="flex-1 flex flex-col bg-gray-50">
      <!-- 顶部栏 -->
      <header class="flex-shrink-0 border-b border-gray-100 bg-white px-6 py-3 flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold text-gray-800">智能工作台</h2>
          <p class="text-xs text-gray-400">基于双轨 RAG 的农业知识问答与决策支持</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-green-50 text-green-700 border border-green-200">
            <span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
            在线
          </span>
        </div>
      </header>

      <!-- 消息区域 -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto">
        <!-- 欢迎页 -->
        <div v-if="showWelcome()" class="flex flex-col items-center justify-center h-full px-4">
          <div class="text-center mb-8">
            <div class="w-16 h-16 rounded-2xl bg-green-600 flex items-center justify-center text-3xl text-white mx-auto mb-4">农</div>
            <h3 class="text-xl font-bold text-gray-800 mb-2">欢迎使用农知睿策</h3>
            <p class="text-sm text-gray-500 max-w-md">我是您的专业农业知识助手，可以为您解答种植、病虫害、施肥、行情等农业问题</p>
          </div>
          <SkillCard @select="handleSkillSelect" />
        </div>

        <!-- 对话消息列表 -->
        <template v-else>
          <div v-for="(msg, i) in getMessages()" :key="i">
            <ChatBubble :message="msg" />
          </div>

          <!-- 加载动画 -->
          <div v-if="chatStore.isLoading" class="flex items-center gap-2 px-8 py-3">
            <div class="flex gap-1">
              <span class="w-2 h-2 rounded-full bg-green-400 animate-bounce" style="animation-delay: 0ms"></span>
              <span class="w-2 h-2 rounded-full bg-green-400 animate-bounce" style="animation-delay: 150ms"></span>
              <span class="w-2 h-2 rounded-full bg-green-400 animate-bounce" style="animation-delay: 300ms"></span>
            </div>
            <span class="text-xs text-gray-400">正在思考...</span>
          </div>
        </template>
      </div>

      <!-- 输入区域 -->
      <ChatInput :disabled="chatStore.isLoading" @send="handleSend" />
    </main>
  </div>
</template>
