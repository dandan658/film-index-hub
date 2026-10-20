<template>
  <nav class="app-bottom-nav">
    <div class="nav-content">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
      >
        <span class="nav-label">{{ item.label }}</span>
      </router-link>
      
      <!-- 添加按钮 -->
      <button type="button" class="nav-item add-btn" @click="showAddTaskDialog" aria-label="添加转存任务">
        <span class="nav-label">添加</span>
      </button>
    </div>
    
    <!-- 背景安全区域 -->
    <div class="safe-area-padding"></div>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useTaskStore, useUserStore } from '@/stores'

// Props & Emits
interface Emits {
  (e: 'add-task'): void
}

const emit = defineEmits<Emits>()

// Composables
const route = useRoute()
const taskStore = useTaskStore()
const userStore = useUserStore()

// Store 数据
const { taskStats } = storeToRefs(taskStore)
const { userStats } = storeToRefs(userStore)

// 导航项目
const navItems = computed(() => [
  {
    path: '/dashboard',
    label: '首页',
    badge: 0
  },
  {
    path: '/tasks',
    label: '任务',
    badge: taskStats.value.running
  },
  {
    path: '/users',
    label: '用户',
    badge: userStats.value.invalid
  },
  {path:'/media',label:'媒体',badge:0},
  {
    path: '/settings',
    label: '设置',
    badge: 0
  }
] satisfies Array<{ path: string; label: string; badge: number }>)

// 方法
const isActive = (path: string) => {
  return route.path === path || (path !== '/' && route.path.startsWith(path))
}

const showAddTaskDialog = () => {
  emit('add-task')
}
</script>

<style scoped>
.app-bottom-nav { position:fixed; z-index:1000; bottom:max(12px,env(safe-area-inset-bottom)); left:12px; right:12px; border-radius:28px; padding:6px; }
.nav-content { display:flex; align-items:center; height:64px; gap:3px; }
.nav-item { appearance:none; border:0; font-family:inherit; background:transparent; flex:1; min-width:0; height:58px; display:flex; flex-direction:column; gap:5px; align-items:center; justify-content:center; color:var(--text-secondary); text-decoration:none; border-radius:21px; cursor:pointer; transition:background .2s ease,color .2s ease,transform .2s var(--ios-ease); }
.nav-item.active { background:var(--accent-soft); color:var(--el-color-primary); }
.nav-item:active { transform:scale(.94); }
.nav-icon { height:24px; display:flex; align-items:center; justify-content:center; }
.nav-label { font-size:11px; font-weight:600; }
.add-icon { width:34px; height:34px; border-radius:12px; background:var(--el-color-primary); color:white; }
.add-btn { background:var(--el-color-primary);color:white; }.nav-label { font-size:13px; }.nav-item { position:relative; }
.safe-area-padding { display:none; }
.nav-icon :deep(.el-badge__content) { height:16px; min-width:16px; padding:0 4px; font-size:10px; line-height:16px; }
</style>
