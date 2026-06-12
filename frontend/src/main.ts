import { createApp } from "vue";
import { createPinia } from "pinia";
import { client } from "@/client/client.gen";
import App from "./App.vue";
import router from "./router";
import "./assets/main.css";

// SDK 走同源代理（Vite proxy /api → backend），避免开发期跨域
client.setConfig({ baseUrl: window.location.origin });

const app = createApp(App);

app.use(createPinia());
app.use(router);

app.mount("#app");
