<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{
  disabled?: boolean;
}>();

const emit = defineEmits<{
  send: [message: string];
}>();

const inputText = ref("");

function handleSubmit(): void {
  const text = inputText.value.trim();
  if (!text || props.disabled) return;
  emit("send", text);
  inputText.value = "";
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
}
</script>

<template>
  <div class="border-t border-gray-100 bg-white px-4 py-3">
    <div class="flex items-end gap-2 max-w-3xl mx-auto">
      <textarea
        v-model="inputText"
        :disabled="disabled"
        :placeholder="disabled ? 'AI 正在思考中...' : '输入您的农业问题...'"
        rows="1"
        class="flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm focus:outline-none focus:border-green-400 focus:ring-1 focus:ring-green-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        @keydown="handleKeydown"
      />
      <button
        :disabled="disabled || !inputText.trim()"
        @click="handleSubmit"
        class="flex-shrink-0 w-10 h-10 rounded-xl bg-green-600 text-white flex items-center justify-center hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19V5m-7 7l7-7 7 7"/>
        </svg>
      </button>
    </div>
    <p class="text-center text-xs text-gray-400 mt-2">
      农知睿策仅提供农业领域知识问答 · 按 Enter 发送，Shift+Enter 换行
    </p>
  </div>
</template>
