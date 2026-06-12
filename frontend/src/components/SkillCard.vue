<script setup lang="ts">
interface Skill {
  id: string;
  name: string;
  icon: string;
  description: string;
  prompt: string;
}

const skills: Skill[] = [
  {
    id: "pest_expert",
    name: "病虫害诊断",
    icon: "🦠",
    description: "智能诊断作物病虫害，给出生物/化学防治方案",
    prompt: "我的作物出现了以下病征：",
  },
  {
    id: "fertilizer_calc",
    name: "施肥决策",
    icon: "🌾",
    description: "根据作物和土壤数据，计算精准氮磷钾配比",
    prompt: "请帮我制定施肥方案，我的作物是：",
  },
  {
    id: "market_analyzer",
    name: "行情分析",
    icon: "📈",
    description: "获取农产品最新市场价格走势与供需预测",
    prompt: "请分析以下农产品的市场行情：",
  },
];

const emit = defineEmits<{
  select: [prompt: string];
}>();

function handleSkillClick(skill: Skill): void {
  emit("select", skill.prompt);
}
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 px-4 py-3">
    <button
      v-for="skill in skills"
      :key="skill.id"
      @click="handleSkillClick(skill)"
      class="group flex flex-col items-start gap-1.5 p-4 rounded-xl border border-gray-100 bg-white hover:border-green-300 hover:shadow-md transition-all duration-200 text-left cursor-pointer"
    >
      <div class="flex items-center gap-2">
        <span class="text-2xl">{{ skill.icon }}</span>
        <span class="font-semibold text-sm text-gray-800 group-hover:text-green-700">{{ skill.name }}</span>
      </div>
      <p class="text-xs text-gray-500 leading-relaxed">{{ skill.description }}</p>
    </button>
  </div>
</template>
