<script setup lang="ts">
import { type ComponentPublicInstance, nextTick, ref } from "vue";
import { useChatStore } from "@/stores/chat";

const chatStore = useChatStore();
/** 二次确认中的待删除 id（首次点进入确认态，再次点才真删） */
const pendingDeleteId = ref<string>("");
/** 正在重命名的会话 id */
const editingId = ref<string>("");
/** 重命名输入框的值 */
const editingTitle = ref<string>("");
/** 输入框 DOM 引用（函数式 ref，绕过 v-for 数组行为） */
const editInputRef = ref<HTMLInputElement | null>(null);

function setEditInput(el: Element | ComponentPublicInstance | null): void {
  editInputRef.value = el as HTMLInputElement | null;
}

function handleNewChat(): void {
  void chatStore.createConversation();
}

function handleSelect(id: string): void {
  if (editingId.value === id) return;
  void chatStore.switchConversation(id);
}

function handleDelete(id: string): void {
  if (editingId.value === id) return;
  if (pendingDeleteId.value === id) {
    pendingDeleteId.value = "";
    void chatStore.deleteConversation(id);
  } else {
    pendingDeleteId.value = id;
    window.setTimeout(() => {
      if (pendingDeleteId.value === id) pendingDeleteId.value = "";
    }, 3000);
  }
}

/** 进入重命名模式 */
function startRename(id: string, currentTitle: string): void {
  editingId.value = id;
  editingTitle.value = currentTitle;
  pendingDeleteId.value = "";
  void nextTick(() => {
    editInputRef.value?.focus();
    editInputRef.value?.select();
  });
}

/** 提交重命名 */
function commitRename(id: string): void {
  const trimmed = editingTitle.value.trim();
  if (!trimmed) {
    cancelRename();
    return;
  }
  const conv = chatStore.conversations.find((c) => c.id === id);
  if (conv && trimmed !== conv.title) {
    void chatStore.renameConversation(id, trimmed);
  }
  editingId.value = "";
  editingTitle.value = "";
}

/** 取消重命名 */
function cancelRename(): void {
  editingId.value = "";
  editingTitle.value = "";
}

/** 键盘事件 */
function handleRenameKeydown(e: KeyboardEvent, id: string): void {
  if (e.key === "Enter") {
    e.preventDefault();
    commitRename(id);
  } else if (e.key === "Escape") {
    e.preventDefault();
    cancelRename();
  }
}

function formatDate(value: string | number): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}
</script>

<template>
  <aside class="w-64 flex-shrink-0 bg-gray-900 text-white flex flex-col h-full">
    <!-- Logo 区域 -->
    <div class="px-4 py-5 border-b border-gray-700">
      <div class="flex items-center gap-2">
        <div class="w-8 h-8 rounded-lg bg-green-600 flex items-center justify-center text-sm font-bold">农</div>
        <div>
          <h1 class="text-sm font-bold">农知睿策</h1>
          <p class="text-xs text-gray-400">AgriMind</p>
        </div>
      </div>
    </div>

    <!-- 新建对话按钮 -->
    <div class="px-3 py-3">
      <button
        @click="handleNewChat"
        class="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-gray-600 text-sm hover:bg-gray-800 transition-colors cursor-pointer"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        新建对话
      </button>
    </div>

    <!-- 会话列表 -->
    <nav class="flex-1 overflow-y-auto px-3 space-y-1">
      <!-- 加载中状态 -->
      <div v-if="!chatStore.isLoaded" class="flex flex-col items-center justify-center py-8">
        <div class="flex gap-1">
          <span class="w-2 h-2 rounded-full bg-green-400 animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 rounded-full bg-green-400 animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 rounded-full bg-green-400 animate-bounce" style="animation-delay: 300ms"></span>
        </div>
        <span class="text-xs text-gray-400 mt-2">加载中...</span>
      </div>

      <!-- 空状态 -->
      <div v-else-if="chatStore.conversations.length === 0" class="flex flex-col items-center justify-center py-8">
        <svg class="w-10 h-10 text-gray-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
        </svg>
        <span class="text-xs text-gray-400">暂无对话</span>
      </div>

      <!-- 会话列表 -->
      <div
        v-else
        v-for="conv in chatStore.conversations"
        :key="conv.id"
        @click="handleSelect(conv.id)"
        :class="[
          'w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-left transition-colors group cursor-pointer',
          conv.id === chatStore.activeConversationId
            ? 'bg-gray-700 text-white'
            : 'text-gray-300 hover:bg-gray-800',
        ]"
        role="button"
        tabindex="0"
      >
        <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
        </svg>

        <!-- 重命名输入框 / 标题展示 -->
        <input
          v-if="editingId === conv.id"
          :ref="setEditInput"
          v-model="editingTitle"
          class="flex-1 min-w-0 bg-gray-600 text-white text-sm px-1.5 py-0.5 rounded border border-green-400 outline-none"
          @click.stop
          @keydown="handleRenameKeydown($event, conv.id)"
          @blur="commitRename(conv.id)"
          maxlength="200"
        />
        <span v-else class="flex-1 truncate">{{ conv.title }}</span>

        <span v-if="editingId !== conv.id" class="text-xs text-gray-500 flex-shrink-0">{{ formatDate(conv.updatedAt) }}</span>

        <!-- 重命名按钮 -->
        <button
          v-if="editingId !== conv.id"
          @click.stop="startRename(conv.id, conv.title)"
          class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-green-400 transition-colors cursor-pointer flex-shrink-0"
          title="重命名"
          aria-label="重命名对话"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
          </svg>
        </button>

        <!-- 删除按钮 -->
        <button
          v-if="editingId !== conv.id"
          @click.stop="handleDelete(conv.id)"
          :class="[
            'text-[11px] font-medium px-1.5 py-0.5 rounded transition-colors cursor-pointer flex-shrink-0',
            pendingDeleteId === conv.id
              ? 'bg-red-500 text-white opacity-100'
              : 'opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-400',
          ]"
          :title="pendingDeleteId === conv.id ? '再点一次确认删除' : '删除对话'"
          :aria-label="pendingDeleteId === conv.id ? '确认删除' : '删除对话'"
        >
          {{ pendingDeleteId === conv.id ? "确认" : "×" }}
        </button>
      </div>
    </nav>

    <!-- 底部导航 -->
    <div class="border-t border-gray-700 px-3 py-3 space-y-1">
      <router-link
        to="/"
        class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 hover:bg-gray-800 transition-colors"
        active-class="bg-gray-700 text-white"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
        </svg>
        智能工作台
      </router-link>
      <router-link
        to="/knowledge"
        class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 hover:bg-gray-800 transition-colors"
        active-class="bg-gray-700 text-white"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
        </svg>
        知识库管理
      </router-link>
    </div>
  </aside>
</template>
