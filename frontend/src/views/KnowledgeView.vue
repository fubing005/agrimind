<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useChatStore } from "@/stores/chat";
import {
  getInfoApiV1KnowledgeInfoGet,
  uploadKnowledgeDocumentApiV1KnowledgeUploadPost,
} from "@/client/sdk.gen";
import type { KnowledgeBaseInfo, KnowledgeUploadResponse } from "@/client/types.gen";
import Sidebar from "@/components/Sidebar.vue";

const chatStore = useChatStore();
const kbInfo = ref<KnowledgeBaseInfo>({
  name: "农知睿策农业知识库",
  document_count: 0,
  chunk_count: 0,
});

const isUploading = ref(false);
const uploadResult = ref<KnowledgeUploadResponse | null>(null);
const uploadError = ref("");
const selectedFile = ref<File | null>(null);

onMounted(async () => {
  try {
    const { data } = await getInfoApiV1KnowledgeInfoGet({ throwOnError: true });
    kbInfo.value = data;
  } catch {
    // 后端未启动时使用默认值
  }
  // 走 store，让侧边栏能正确响应式更新会话列表
  await chatStore.loadConversationsFromBackend();
});

function handleFileChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0]!;
    uploadResult.value = null;
    uploadError.value = "";
  }
}

async function handleUpload(): Promise<void> {
  if (!selectedFile.value) return;

  isUploading.value = true;
  uploadResult.value = null;
  uploadError.value = "";

  try {
    const { data, response } = await uploadKnowledgeDocumentApiV1KnowledgeUploadPost({
      body: { file: selectedFile.value },
      throwOnError: true,
    });
    if (!response.ok) throw new Error(`上传失败 (HTTP ${response.status})`);
    uploadResult.value = data;

    // 刷新知识库信息
    const { data: info } = await getInfoApiV1KnowledgeInfoGet({ throwOnError: true });
    kbInfo.value = info;

    selectedFile.value = null;
  } catch (err) {
    uploadError.value = err instanceof Error ? err.message : "上传失败";
  } finally {
    isUploading.value = false;
  }
}

const supportedFormats = ["TXT", "MD", "PDF", "CSV", "JSON"];
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <!-- 侧边栏 -->
    <Sidebar />

    <!-- 主内容区 -->
    <main class="flex-1 overflow-y-auto bg-gray-50">
      <!-- 顶部栏 -->
      <header class="border-b border-gray-100 bg-white px-6 py-3">
        <h2 class="text-base font-semibold text-gray-800">知识库管理</h2>
        <p class="text-xs text-gray-400">上传农业文档，构建本地专业知识库</p>
      </header>

      <div class="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <!-- 知识库信息卡片 -->
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center text-xl">📚</div>
            <div>
              <h3 class="font-semibold text-gray-800">{{ kbInfo.name }}</h3>
              <p class="text-xs text-gray-400">基于 LlamaIndex + ChromaDB 向量检索</p>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="bg-gray-50 rounded-lg p-4 text-center">
              <p class="text-2xl font-bold text-green-600">{{ kbInfo.document_count }}</p>
              <p class="text-xs text-gray-500 mt-1">文档数量</p>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
              <p class="text-2xl font-bold text-green-600">{{ kbInfo.chunk_count }}</p>
              <p class="text-xs text-gray-500 mt-1">知识分块</p>
            </div>
          </div>
        </div>

        <!-- 文档上传卡片 -->
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h3 class="font-semibold text-gray-800 mb-4">上传文档</h3>
          <p class="text-sm text-gray-500 mb-4">
            支持格式：{{ supportedFormats.join("、") }}，上传后将自动分块、向量化并存入知识库
          </p>

          <div class="space-y-4">
            <div class="flex items-center gap-3">
              <label
                class="flex-1 flex items-center gap-2 px-4 py-3 rounded-lg border-2 border-dashed border-gray-200 hover:border-green-400 cursor-pointer transition-colors"
                :class="{ 'border-green-400 bg-green-50': selectedFile }"
              >
                <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                </svg>
                <span class="text-sm text-gray-500">
                  {{ selectedFile ? selectedFile.name : "点击选择文件" }}
                </span>
                <input type="file" class="hidden" :accept="supportedFormats.map(f => `.${f.toLowerCase()}`).join(',')" @change="handleFileChange" />
              </label>

              <button
                :disabled="!selectedFile || isUploading"
                @click="handleUpload"
                class="px-6 py-3 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
              >
                {{ isUploading ? "上传中..." : "上传" }}
              </button>
            </div>

            <!-- 上传成功提示 -->
            <div v-if="uploadResult?.success" class="flex items-start gap-2 p-3 rounded-lg bg-green-50 border border-green-200">
              <svg class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
              </svg>
              <div>
                <p class="text-sm font-medium text-green-800">{{ uploadResult.message }}</p>
                <p v-if="uploadResult.chunk_count" class="text-xs text-green-600 mt-1">
                  已生成 {{ uploadResult.chunk_count }} 个知识分块
                </p>
              </div>
            </div>

            <!-- 上传失败提示 -->
            <div v-if="uploadError" class="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200">
              <svg class="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
              </svg>
              <p class="text-sm text-red-800">{{ uploadError }}</p>
            </div>
          </div>
        </div>

        <!-- 使用说明 -->
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h3 class="font-semibold text-gray-800 mb-3">使用说明</h3>
          <ul class="space-y-2 text-sm text-gray-600">
            <li class="flex items-start gap-2">
              <span class="text-green-600 font-bold">1.</span>
              上传农业文献、种植手册、病虫害防治指南等文档
            </li>
            <li class="flex items-start gap-2">
              <span class="text-green-600 font-bold">2.</span>
              系统将自动分块并向量化，存入本地 ChromaDB 知识库
            </li>
            <li class="flex items-start gap-2">
              <span class="text-green-600 font-bold">3.</span>
              在智能工作台提问时，系统将优先检索本地知识库
            </li>
            <li class="flex items-start gap-2">
              <span class="text-green-600 font-bold">4.</span>
              若本地知识不足，系统将自动触发联网搜索补充
            </li>
          </ul>
        </div>
      </div>
    </main>
  </div>
</template>
