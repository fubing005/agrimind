<script setup lang="ts">
import { computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import type { ChatMessage } from "@/stores/chat";

const props = defineProps<{
  message: ChatMessage;
}>();

/** 格式化时间戳 */
function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

/** 渲染Markdown内容 */
const renderedContent = computed(() => {
  if (!props.message.content) return "";
  
  // 配置marked选项
  marked.setOptions({
    breaks: true, // 支持换行符
    gfm: true, // 启用GitHub风格Markdown
  });
  
  // 将markdown转换为HTML
  const html = marked.parse(props.message.content) as string;
  
  // 使用DOMPurify净化HTML，防止XSS攻击
  return DOMPurify.sanitize(html);
});
</script>

<template>
  <div
    :class="[
      'flex gap-3 px-4 py-3',
      message.role === 'user' ? 'flex-row-reverse' : 'flex-row',
    ]"
  >
    <!-- 头像 -->
    <div
      :class="[
        'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold',
        message.role === 'user'
          ? 'bg-green-600 text-white'
          : 'bg-emerald-100 text-green-700',
      ]"
    >
      {{ message.role === "user" ? "我" : "农" }}
    </div>

    <!-- 消息内容 -->
    <div :class="['max-w-[75%] flex flex-col', message.role === 'user' ? 'items-end' : 'items-start']">
      <div
        :class="[
          'rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
          message.role === 'user'
            ? 'bg-green-600 text-white rounded-tr-sm'
            : 'bg-white border border-gray-100 shadow-sm rounded-tl-sm',
          message.blocked ? 'border-amber-300 bg-amber-50' : '',
        ]"
      >
        <!-- 拦截提示 -->
        <div v-if="message.blocked" class="flex items-center gap-1.5 mb-1 text-amber-600 text-xs font-medium">
          <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          非农业问题已拦截
        </div>

        <!-- 消息正文 -->
        <div class="markdown-body" v-html="renderedContent" />

        <!-- 技能标签 -->
        <div
          v-if="message.skillUsed"
          class="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-green-50 text-green-700 border border-green-200"
        >
          <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z"/>
          </svg>
          {{ message.skillUsed === "pest_expert" ? "病虫害诊断" : message.skillUsed === "fertilizer_calc" ? "施肥决策" : "行情分析" }}
        </div>
      </div>

      <!-- 来源引用 -->
      <div v-if="message.sources && message.sources.length > 0" class="mt-1.5 text-xs text-gray-400 max-w-full">
        <span>来源：</span>
        <span v-for="(src, i) in message.sources" :key="i">
          <a v-if="src.startsWith('http')" :href="src" target="_blank" class="text-green-600 hover:underline truncate inline-block max-w-[200px] align-bottom">{{ src }}</a>
          <span v-else>{{ src }}</span>
          <span v-if="i < message.sources!.length - 1">、</span>
        </span>
      </div>

      <!-- 时间 -->
      <span class="mt-1 text-xs text-gray-300">{{ formatTime(message.timestamp) }}</span>
    </div>
  </div>
</template>
