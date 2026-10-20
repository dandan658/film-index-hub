<template>
  <div class="app-layout" :class="{ 'mobile-layout': isMobile, 'sidebar-collapsed': isCollapsed }">
    <!-- 桌面端布局 -->
    <template v-if="!isMobile">
      <!-- 侧边栏 -->
      <AppSidebar
        @add-task="handleAddTask"
        @collapse="handleSidebarCollapse"
      />
      
      <!-- 主要内容区域 -->
      <div class="main-wrapper">
        <!-- 顶部导航 -->
        <AppHeader />
        
        <!-- 内容区域 -->
        <main class="main-content">
          <div class="content-container">
            <router-view v-slot="{ Component, route }">
              <Transition
                name="ios-page"
                mode="out-in"
                appear
              >
                <component
                  :is="Component"
                  :key="route.path"
                  class="page-component"
                />
              </Transition>
            </router-view>
          </div>
        </main>
      </div>
    </template>
    
    <!-- 移动端布局 -->
    <template v-else>
      <!-- 顶部导航 -->
      <AppHeader />
      
      <!-- 主要内容区域 -->
      <main class="mobile-main-content">
        <div class="mobile-content-container">
          <router-view v-slot="{ Component, route }">
            <Transition
              name="ios-page"
              mode="out-in"
              appear
            >
              <component
                :is="Component"
                :key="route.path"
                class="page-component"
              />
            </Transition>
          </router-view>
        </div>
      </main>
      
      <!-- 底部导航 -->
      <AppBottomNav @add-task="handleAddTask" />
      
      <!-- 移动端侧边栏抽屉已移除，使用底部导航代替 -->
    </template>
    
    <!-- 全局加载遮罩 -->
    <div v-if="globalLoading" class="global-loading">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <p>加载中...</p>
    </div>
    
    
    <!-- 全局消息提示容器 -->
    <div id="message-container"></div>
    <AddTaskDialog v-if="showGlobalAddTask" v-model="showGlobalAddTask" @success="taskStore.fetchTasks()" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch, defineAsyncComponent } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore, useTaskStore, useUserStore } from '@/stores'
import { isMobile as checkIsMobile } from '@/utils/helpers'
import { appStorage } from '@/utils/storage'
import {warmupCommonViews} from '@/services/warmup'
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'
import AppBottomNav from './AppBottomNav.vue'
const AddTaskDialog = defineAsyncComponent(() => import('@/components/business/AddTaskDialog.vue'))

// Composables
const authStore = useAuthStore()
const taskStore = useTaskStore()
const userStore = useUserStore()

// Store 数据
const { loading: authLoading } = storeToRefs(authStore)

// 响应式状态
const isMobile = ref(checkIsMobile())
const isCollapsed = ref(window.innerWidth < 1100)
const showGlobalAddTask = ref(false)

// 计算属性
const globalLoading = computed(() => {
  return authLoading.value
})

// 方法
const handleAddTask = () => {
  // 触发全局添加任务事件
  showGlobalAddTask.value = true
}

const handleSidebarCollapse = (collapsed: boolean) => {
  isCollapsed.value = collapsed
}

// 移动端侧边栏相关方法已移除，使用底部导航代替

const handleResize = () => {
  const mobile = checkIsMobile()
  if (mobile !== isMobile.value) {
    isMobile.value = mobile
  }
}

const initializeApp = async () => {
  try {
    // 初始化用户数据
    await Promise.all([
      taskStore.fetchTasks(),
      userStore.init()
    ])
  } catch (error) {
    console.error('应用初始化失败:', error)
  }
}

// 生命周期
onMounted(async () => {
  // 恢复侧边栏折叠状态
  const savedCollapsed = appStorage.getItem<boolean>('sidebar-collapsed')
  if (savedCollapsed !== null) {
    isCollapsed.value = savedCollapsed || window.innerWidth < 1100
  }
  
  // 监听窗口大小变化
  window.addEventListener('resize', handleResize)
  
  // 监听认证状态变化，只在用户已认证时初始化应用数据
  watch(
    () => authStore.isLoggedIn,
    async (isLoggedIn) => {
      if (isLoggedIn) {
        await nextTick()
        await initializeApp()
        warmupCommonViews()
      }
    },
    { immediate: true } // 立即检查当前认证状态
  )
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.app-layout { width:100%; height:100vh; height:100dvh; overflow:hidden; background:transparent; }
.main-wrapper { margin-left:272px; height:100%; display:flex; flex-direction:column; transition:margin-left .3s var(--ios-ease); min-width:0; }
.sidebar-collapsed .main-wrapper { margin-left:104px; }
.main-content { flex:1; min-height:0; margin-top:96px; overflow:hidden; }
.content-container { height:100%; overflow:auto; overscroll-behavior:contain; scrollbar-gutter:stable; }
.page-component { min-height:100%; }
.mobile-main-content { height:100dvh; padding:88px 0 calc(100px + env(safe-area-inset-bottom)); overflow:hidden; }
.mobile-content-container { height:100%; overflow:auto; overscroll-behavior:contain; }
.global-loading { position:fixed; inset:0; z-index:9999; display:grid; place-content:center; justify-items:center; gap:12px; background:var(--glass-panel); }
.loading-icon { font-size:28px; color:var(--el-color-primary); animation:loading-rotate 1s linear infinite; }
@keyframes loading-rotate { to { transform:rotate(360deg); } }
@media(max-width:1099px) and (min-width:768px) { .main-wrapper { margin-left:104px; } }
@media(max-width:767px) { .app-layout { height:100dvh; } }
</style>
