import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "workspace",
    component: () => import("@/views/WorkspaceView.vue"),
    meta: { title: "智能工作台" },
  },
  {
    path: "/knowledge",
    name: "knowledge",
    component: () => import("@/views/KnowledgeView.vue"),
    meta: { title: "知识库管理" },
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach((to) => {
  const title = (to.meta.title as string) || "农知睿策";
  document.title = `${title} - 农知睿策`;
});

export default router;
