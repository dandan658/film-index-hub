<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <div class="sidebar-content">
      <!-- 侧边栏头部 -->
      <div class="sidebar-header">
        <div v-if="!isCollapsed" class="header-content">
          <img src="/favicon/favicon.svg" alt="Logo" class="sidebar-logo" />
          <h2 class="sidebar-title">Film Index</h2>
        </div>
        
        <!-- 折叠按钮 -->
        <el-button
          v-if="viewportWidth >= 1100"
          type="text"
          class="collapse-btn" :aria-label="isCollapsed ? '展开侧栏' : '收起侧栏'"
          @click="toggleCollapse"
        >
          <el-icon>
            <component :is="isCollapsed ? 'Expand' : 'Fold'" />
          </el-icon>
        </el-button>
        <img v-else src="/favicon/favicon.svg" alt="自动转存" class="sidebar-logo" />
      </div>
      
      <!-- 导航菜单 -->
      <nav class="sidebar-nav">
        <el-menu
          :default-active="activeRoute"
          :collapse="false"
          :unique-opened="true"
          class="sidebar-menu"
          @select="handleMenuSelect"
        >
          <!-- 仪表盘 -->
          <el-menu-item index="/dashboard" class="menu-item" aria-label="仪表盘">
            
            <template #title>仪表盘</template>
          </el-menu-item>
          
          <!-- 任务管理 -->
          <el-menu-item index="/tasks" class="menu-item" aria-label="任务管理">
            
            <template #title>
              <span>百度订阅</span>
              <span v-if="taskStats.running > 0" class="menu-count" :aria-label="`${taskStats.running} 个任务运行中`">{{ taskStats.running > 99 ? '99+' : taskStats.running }}</span>
            </template>
          </el-menu-item>
          
          <!-- 用户管理 -->
          <el-menu-item index="/users" class="menu-item" aria-label="用户管理">
            
            <template #title>
              <span>网盘账号</span>
              <el-tag
                v-if="userStats.invalid > 0"
                type="danger"
                size="small"
                class="menu-tag"
              >
                {{ userStats.invalid }}
              </el-tag>
            </template>
          </el-menu-item>
          
          <!-- 系统设置 -->
          <el-menu-item index="/settings" class="menu-item" aria-label="系统设置">
            
            <template #title>系统设置</template>
          </el-menu-item>
          <el-sub-menu index="media-workspace"><template #title><span>媒体整理</span></template>
            <el-menu-item v-for="item in mediaPages.slice(0,5)" :key="item.page" :index="'/media?page='+item.page"><span>{{ item.label }}</span></el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="media-settings"><template #title><span>媒体设置</span></template>
            <el-menu-item v-for="item in mediaPages.slice(5)" :key="item.page" :index="'/media?page='+item.page"><span>{{ item.label }}</span></el-menu-item>
          </el-sub-menu>
        </el-menu>
      </nav>
      
      <!-- 侧边栏底部 -->
      <div class="sidebar-footer">
        <!-- 系统状态 -->
        <div v-if="!isCollapsed && route.path !== '/media'" class="system-status">
          <div class="status-item">
            <span class="status-label">轮询状态</span>
            <el-tag
              :type="pollingStatus ? 'success' : 'danger'"
              size="small"
              class="status-value"
            >
              {{ pollingStatus ? '运行中' : '已停止' }}
            </el-tag>
          </div>
          
          <div v-if="currentUser" class="status-item">
            <span class="status-label">当前用户</span>
            <span class="status-value user-name">{{ currentUser }}</span>
          </div>
          
          <div v-if="userQuota" class="quota-info">
            <div class="quota-text">
              <span class="quota-label">存储空间</span>
              <span class="quota-used">{{ userQuota.used_formatted }}</span>
              <span class="quota-divider">/</span>
              <span class="quota-total">{{ userQuota.total_formatted }}</span>
            </div>
            <el-progress
              :percentage="quotaPercentage"
              :stroke-width="4"
              :show-text="false"
              class="quota-progress"
            />
          </div>
        </div>
        
        <!-- 快捷操作 -->
        <div v-if="route.path !== '/media'" class="quick-actions">
          <el-tooltip content="添加任务" :disabled="!isCollapsed">
            <el-button
              type="primary"
              :icon="Plus"
              :class="{ 'collapsed-btn': isCollapsed }"
              @click="showAddTaskDialog"
            >
              <span v-if="!isCollapsed">添加任务</span>
            </el-button>
          </el-tooltip>
        </div>
        
        <!-- 版本信息 -->
        <div v-if="!isCollapsed" class="version-section">
          <div class="version-item" @click="handleVersionCheck">
            <span class="version-label">版本</span>
            <el-badge :is-dot="hasUpdate" type="warning">
              <span class="version-number">{{ APP_VERSION }}</span>
            </el-badge>
          </div>
          
          <div v-if="hasUpdate" class="update-notice">
            <el-button type="text" size="small" @click="handleVersionCheck">
              <el-icon><Download /></el-icon>
              发现新版本
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import {mediaPages} from '@/config/mediaPages'
import { useRouter, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useTaskStore, useUserStore, useVersionStore } from '@/stores'
import { usePolling } from '@/composables/usePolling'
import { APP_VERSION } from '@/config/version'
import { appStorage } from '@/utils/storage'
import { Plus, Download } from '@element-plus/icons-vue'

// Props & Emits
interface Emits {
  (e: 'add-task'): void
  (e: 'collapse', value: boolean): void
}

const emit = defineEmits<Emits>()

// Composables
const router = useRouter()
const route = useRoute()
const taskStore = useTaskStore()
const userStore = useUserStore()
const versionStore = useVersionStore()

// Store 数据
const { taskStats } = storeToRefs(taskStore)
const { userStats, currentUser, userQuota } = storeToRefs(userStore)
const { hasUpdate } = storeToRefs(versionStore)

// 轮询状态
const { isRunning: pollingStatus } = usePolling()

// 版本检查方法
const handleVersionCheck = () => {
  versionStore.checkForUpdates() // 检查版本
}

// 状态
const userCollapsed = ref(appStorage.getItem<boolean>('sidebar-collapsed') ?? false)
const viewportWidth = ref(window.innerWidth)
const isCollapsed = computed(() => userCollapsed.value || viewportWidth.value < 1100)
const handleResize = () => { viewportWidth.value = window.innerWidth }
watch(isCollapsed, value => emit('collapse', value), { immediate: true })

// 计算属性
const activeRoute = computed(() => {
  return route.path === "/media" ? "/media?page=" + (route.query.page || "mediafile") : route.path
})

const quotaPercentage = computed(() => {
  if (!userQuota.value) return 0
  return Math.round((userQuota.value.used / userQuota.value.total) * 100)
})

// 方法
const toggleCollapse = () => {
  userCollapsed.value = !userCollapsed.value
  appStorage.setItem('sidebar-collapsed', userCollapsed.value)
}

const handleMenuSelect = (index: string) => {
  router.push(index)
}

const showAddTaskDialog = () => {
  emit('add-task')
}

onMounted(() => window.addEventListener('resize', handleResize, { passive: true }))
onUnmounted(() => window.removeEventListener('resize', handleResize))
</script>

<style scoped>
.app-sidebar { position:fixed; top:96px; left:16px; bottom:16px; width:240px; z-index:990; border-radius:26px; overflow:hidden; transition:width .3s var(--ios-ease); }
.app-sidebar.collapsed { width:72px; }
.sidebar-content { height:100%; display:flex; flex-direction:column; min-height:0; }
.sidebar-header { height:68px; padding:0 18px; display:flex; align-items:center; gap:8px; flex-shrink:0; }
.header-content { display:flex; align-items:center; gap:10px; min-width:0; flex:1; }
.sidebar-logo { width:26px; height:26px; }
.sidebar-title { font-size:15px; letter-spacing:-.3px; white-space:nowrap; }
.collapse-btn { margin-left:auto; padding:9px; }
.sidebar-nav { flex:1; min-height:0; overflow:auto; padding:0 10px; }
.sidebar-menu { border:0; background:transparent; }
.sidebar-menu.el-menu--collapse { width:100%; }
.sidebar-nav { overflow-x:hidden; }
.sidebar-menu :deep(.el-menu-item) { display:flex; align-items:center; gap:10px; padding:0 14px!important; margin:4px 0; height:48px; line-height:normal; border-radius:15px; color:var(--text-secondary); transition:background-color .18s ease,color .18s ease,transform .18s var(--ios-ease); }
.sidebar-menu :deep(.el-menu-item .el-icon) { margin:0; width:22px; font-size:19px; flex-shrink:0; }
.sidebar-menu :deep(.el-menu-item.is-active) { background:var(--accent-soft); color:var(--el-color-primary); font-weight:600; }
.sidebar-menu :deep(.el-menu-item:hover) { background:var(--hover-surface); }
.menu-count,.menu-tag { position:static; margin-left:auto; flex-shrink:0; display:inline-flex; align-items:center; justify-content:center; min-width:23px; height:23px; padding:0 7px; border-radius:12px; background:var(--el-color-primary); color:white; font-size:11px; font-weight:650; line-height:1; font-variant-numeric:tabular-nums; }
.sidebar-footer { padding:16px; border-top:1px solid var(--glass-separator); flex-shrink:0; }
.system-status { margin-bottom:16px; }
.status-item,.version-item { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:10px; font-size:12px; }
.status-label,.version-label { color:var(--text-secondary); }
.user-name { max-width:110px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.quota-info { padding:12px; margin-top:12px; border-radius:14px; background:var(--inset-surface); }
.quota-text { display:flex; flex-wrap:wrap; gap:4px; margin-bottom:8px; font-size:11px; color:var(--text-secondary); }
.quota-used { color:var(--el-color-primary); }
.quick-actions .el-button { width:100%; height:42px; }
.version-section { margin-top:18px; padding-top:12px; border-top:1px solid var(--glass-separator); }
.version-item { cursor:pointer; margin:0; }
.version-number { font-size:11px; font-variant-numeric:tabular-nums; color:var(--text-secondary); }
.collapsed .sidebar-header { padding:0; justify-content:center; }
.collapsed .collapse-btn { margin:0; }
.collapsed .sidebar-nav { padding:0 8px; }
.collapsed .sidebar-menu :deep(.el-menu-item) { padding:0!important; justify-content:center; }
.collapsed .sidebar-footer { padding:12px 8px; }
.collapsed-btn { padding:0; width:44px!important; margin:auto; display:flex; }
@media(max-width:767px) { .app-sidebar { display:none; } }

.sidebar-menu :deep(.el-sub-menu .el-menu-item){height:36px;line-height:36px;font-size:13px}.sidebar-menu :deep(.el-sub-menu__title){color:var(--text-secondary);height:44px;line-height:44px;padding:0 14px!important}
/* Text-only navigation shares one left edge at every level. */
.sidebar-menu :deep(.el-sub-menu .el-menu){padding:0!important}
.sidebar-menu :deep(.el-sub-menu__title){border-radius:15px;margin:4px 0}
.collapsed .sidebar-menu :deep(.el-sub-menu__title){padding:0!important;justify-content:center;font-size:13px}
.collapsed .sidebar-menu :deep(.el-sub-menu__icon-arrow){display:none}
.collapsed .sidebar-menu :deep(.el-menu-item){font-size:13px}
</style>
