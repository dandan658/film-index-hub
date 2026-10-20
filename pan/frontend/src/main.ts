// Vue 应用入口文件
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { pinia } from './stores'

// Element Plus
import 'element-plus/dist/index.css'
import './styles/glass.css'
import './styles/liquid.css'
import {ArrowDown, Bell, Check, Close, CopyDocument, DCaret, Delete, Document, Download, Edit, Expand, Fold, Hide, InfoFilled, Link, List, Lock, Odometer, Plus, Search, Setting, Share, Sort, User, VideoPlay, View, Warning} from '@element-plus/icons-vue'
const usedIcons={ArrowDown, Bell, Check, Close, CopyDocument, DCaret, Delete, Document, Download, Edit, Expand, Fold, Hide, InfoFilled, Link, List, Lock, Odometer, Plus, Search, Setting, Share, Sort, User, VideoPlay, View, Warning}

// 创建应用实例
const app = createApp(App)

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(usedIcons)) {
  app.component(key, component)
}

// 使用插件
app.use(pinia)
app.use(router)

// 全局错误处理
app.config.errorHandler = (err, _vm, info) => {
  console.error('Vue全局错误:', err, info)
  // 可以在这里添加错误上报逻辑
}

// 全局警告处理
app.config.warnHandler = (msg, _vm, trace) => {
  console.warn('Vue警告:', msg, trace)
}

// 挂载应用
app.mount('#app')

console.log('百度网盘自动转存工具前端已启动')
