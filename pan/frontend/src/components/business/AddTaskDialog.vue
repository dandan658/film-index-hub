<template>
  <el-dialog
    v-model="visible"
    :title="editingTask ? '编辑任务' : '添加任务'"
    width="650px"
    :close-on-click-modal="false"
    class="add-task-dialog"
    :lock-scroll="false"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="formRules"
      label-width="112px"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="任务名称" prop="name">
        <el-input
          v-model="form.name"
          placeholder="自定义名称，例如：牧神记；不会随分享名称变化"
          clearable
          @input="pathNameSync && handlePathNameSync()"
        />
      </el-form-item>

      <el-form-item label="资源类型">
        <el-radio-group v-model="form.media_type">
          <el-radio-button label="tv">电视剧</el-radio-button>
          <el-radio-button label="movie">电影</el-radio-button>
          <el-radio-button label="other">普通文件</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="form.media_type !== 'other'" label="TMDB 资料">
        <TmdbPicker :key="`${visible}-${form.media_type}`" :media-type="form.media_type" :name="form.name" :selected="form.tmdb" @select="selectTmdb" @clear="form.tmdb = null" />
      </el-form-item>
      <el-form-item label="合并子目录">
        <el-switch v-model="form.flatten" />
        <div class="form-help">开启：各级文件统一放入保存目录。关闭：保留子目录结构，仍支持文件重命名。</div>
      </el-form-item>
      <el-form-item label="自动重命名">
        <el-switch v-model="form.auto_rename" :disabled="form.media_type === 'other'" />
        <div class="form-help">根据自定义任务名称整理视频和字幕；无法识别集数会提示并跳过，不会按 4K 等画质数字误命名。</div>
      </el-form-item>
      <el-form-item v-if="form.media_type === 'tv'" label="统一第一季">
        <el-switch v-model="form.force_first_season" />
        <div class="form-help">开启：整个订阅统一使用第一季 S01，覆盖目录、文件名和手动规则中的季数。关闭：自动识别目录和文件名的季数。集数仍按原文件识别；同名文件自动区分，不覆盖。</div>
      </el-form-item>
      <el-form-item v-if="form.media_type === 'tv' && form.auto_rename && !form.force_first_season" label="多季识别">
        <div class="form-help">自动识别各级目录中的第一季、第二季、第三季、Season 02、S03 等。优先使用手动目录规则，其次使用最近的季目录，再使用文件名中的 Sxx，最后才使用下方默认季数。目录中的季数会修正文件名里错误的 S01。</div>
      </el-form-item>
      <el-form-item v-if="form.media_type === 'tv' && form.auto_rename && !form.force_first_season" label="兜底季数">
        <el-input-number v-model="form.season" :min="1" :max="999" :precision="0" />
        <div class="form-help">仅在目录和文件名都未提供季数时使用，不会把整个订阅统一改成第一季。</div>
      </el-form-item>
      <el-form-item v-if="form.auto_rename" label="命名示例">
        <div class="form-help">
          <template v-if="form.media_type === 'tv'">
            <div v-for="(label, index) in ['第一季', '第二季', '第三季']" :key="label">{{ label }}/01.mp4 → {{ form.name || '自定义名称' }} - S{{ String(form.force_first_season ? 1 : index + 1).padStart(2, '0') }}E01.mp4</div>
          </template>
          <div v-else>{{ form.name || '自定义名称' }}.mp4</div>
          保留视频原格式；字幕保留语言后缀；同名冲突自动区分，不覆盖文件。
        </div>
      </el-form-item>
      <el-form-item v-if="form.media_type === 'tv'" label="分季目录">
        <div style="width: 100%">
          <div class="form-help">源路径相对于分享顶层目录。每个子目录可单独设置季数和新目录名；开启统一第一季时，季数和季目录统一为 S01。合并时只使用季数，不创建季目录。001-090 等集数范围不会被误判为季数。</div>
          <div v-for="(rule, index) in form.season_folders" :key="index" class="season-rule">
            <el-input v-model="rule.source" placeholder="源子目录，如 第一季 或 001-090" aria-label="源子目录" />
            <el-input-number v-model="rule.season" :min="1" :max="999" :precision="0" aria-label="对应季数" />
            <el-input v-model="rule.name" :placeholder="`Season ${String(rule.season).padStart(2, '0')}`" aria-label="新目录名称" />
            <el-button type="danger" text @click="form.season_folders.splice(index, 1)">删除</el-button>
          </div>
          <el-button size="small" @click="form.season_folders.push({ source: '', season: 1, name: '' })">添加子目录规则</el-button>
        </div>
      </el-form-item>
      
      <el-form-item label="转存链接" prop="url">
        <el-input
          v-model="form.url"
          placeholder="https://pan.baidu.com/s/xxx?pwd=1234 或 https://pan.baidu.com/share/init?surl=xxx&pwd=1234"
          clearable
          :loading="isParsingUrl"
        />
        <div class="form-help">支持 /s/ 或 /share/init 链接，链接中的提取码会自动填入下方输入框</div>
        <div class="link-actions"><el-button size="small" :loading="isParsingUrl" @click="parseUrl">从链接获取名称（手动）</el-button></div>
      </el-form-item>
      
      <el-form-item label="提取码" prop="pwd">
        <el-input v-model="form.pwd" placeholder="4 位提取码，无提取码可留空" maxlength="4" clearable autocomplete="off" />
        <div class="form-help">与登录密码无关；手动填写的提取码优先。编辑任务时会显示已保存的值。</div>
      </el-form-item>

      <el-form-item label="保存路径" prop="save_dir">
        <div class="path-input-group">
          <el-autocomplete
            v-model="form.save_dir"
            :fetch-suggestions="searchSavePaths"
            placeholder="例如：/我的资源/电影"
            clearable
            value-key="value"
            class="path-select"
          />
          <el-switch
            v-model="pathNameSync"
            class="sync-switch"
            size="small"
            :title="pathNameSync ? '已关联任务名称' : '未关联任务名称'"
            @change="handlePathNameSync"
          />
        </div>
        <div class="form-help">成功转存的文件随任务记忆，云盘中移动或改名后不会重复转存；删除任务会清除记忆。</div>
      </el-form-item>
      
      <el-form-item label="分类" prop="category">
        <el-autocomplete
          v-model="form.category"
          :fetch-suggestions="searchCategories"
          placeholder="可选，用于任务分类"
          clearable
          value-key="value"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="定时规则" prop="cron">
            <div class="cron-input-group">
              <el-autocomplete
                v-model="form.cron"
                :fetch-suggestions="searchCronRules"
                placeholder="可选，使用cron表达式，例如: */5 * * * *"
                clearable
                value-key="value"
                class="cron-select"
              />
              <el-button @click="showCronHelper" size="small">cron助手</el-button>
            </div>
            <div class="form-help">留空则使用默认定时规则，例如：*/5 * * * * 表示每5分钟执行一次</div>
          </el-form-item>

          <el-form-item label="文件过滤" prop="regex_pattern">
            <el-autocomplete
              v-model="form.regex_pattern"
              :fetch-suggestions="searchRegexPatterns"
              placeholder="如：^(\d+)\.mp4$ 用于匹配需要转存的文件"
              clearable
              value-key="value"
              style="width: 100%"
            />
            <div class="form-help">仅匹配文件名，不含目录；留空表示不过滤。自动命名仅整理视频和字幕。</div>
          </el-form-item>

          <el-form-item label="文件重命名" prop="regex_replace">
            <el-autocomplete
              v-model="form.regex_replace"
              :fetch-suggestions="searchRegexReplaces"
              placeholder="如：第\1集.mp4 用于重命名文件"
              clearable
              value-key="value"
              style="width: 100%"
            />
            <div class="form-help">支持 $1 或 \1 捕获组；不填过滤规则时可填固定名称。开启自动命名后，以电影/电视剧命名规则为准。</div>
          </el-form-item>
    </el-form>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          @click="handleSubmit"
        >
          {{ editingTask ? '更新' : '添加' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, reactive, computed, nextTick } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/tasks'
import { apiService } from '@/services'
import type { Task } from '@/types'
import TmdbPicker from './TmdbPicker.vue'

// Props
interface Props {
  modelValue: boolean
  task?: Task | null
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}

const props = withDefaults(defineProps<Props>(), {
  task: null
})

const emit = defineEmits<Emits>()

// Composables
const taskStore = useTaskStore()
const { 
  taskSavePaths, 
  taskCategories, 
  taskCronRules, 
  taskRegexPatterns, 
  taskRegexReplaces,
  getDefaultSavePath
} = storeToRefs(taskStore)

// 状态
const formRef = ref<FormInstance>()
const submitting = ref(false)
const pathNameSync = ref(false) // 仅在用户明确开启时关联自定义名称
const isParsingUrl = ref(false) // URL解析状态

const form = reactive({
  name: '',
  url: '',
  pwd: '',
  save_dir: '',
  category: '',
  cron: '',
  regex_pattern: '',
  regex_replace: '',
  media_type: 'tv' as 'tv' | 'movie' | 'other',
  flatten: true,
  auto_rename: true,
  season: 1,
  force_first_season: false,
  tmdb: null as { id: number; media_type: string; title: string; year: string } | null,
  season_folders: [] as { source: string; season: number; name: string }[]
})

// 高级设置折叠面板状态
// 移除advancedVisible，不再需要折叠面板

const formRules = {
  pwd: [{ pattern: /^$|^[a-zA-Z0-9]{4}$/, message: '提取码应为 4 位字母或数字', trigger: 'blur' }],
  url: [
    { required: true, message: '请输入分享链接', trigger: 'blur' },
    {
      pattern: /^https:\/\/pan\.baidu\.com\/(?:s\/[a-zA-Z0-9_-]+|share\/init\?)/,
      message: '请输入有效的百度网盘分享链接',
      trigger: 'blur'
    }
  ],
  save_dir: [
    { required: true, message: '请输入保存路径', trigger: 'blur' }
  ]
}

// 计算属性
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const editingTask = computed(() => props.task)

// 方法
const resetForm = () => {
  form.name = ''
  form.url = ''
  form.pwd = ''
  form.save_dir = getDefaultSavePath.value || '' // 使用默认路径，如果为空则用空字符串
  form.category = ''
  form.cron = ''
  form.regex_pattern = ''
  form.regex_replace = ''
  form.media_type = 'tv'
  form.flatten = true
  form.auto_rename = true
  form.season = 1
  form.force_first_season = false
  form.tmdb = null
  form.season_folders = []
  pathNameSync.value = false
  formRef.value?.clearValidate()
}

const selectTmdb = (item: any) => {
  pathNameSync.value = false
  form.name = item.title
  form.save_dir = item.save_dir
  form.tmdb = { id: item.id, media_type: item.media_type, title: item.title, year: item.year }
  formRef.value?.clearValidate(['name', 'save_dir'])
}

// 解析转存链接获取文件名
const parseUrl = async () => {
  if (!form.url || isParsingUrl.value) return
  const requestedUrl = form.url
  const requestedName = form.name
  
  try {
    isParsingUrl.value = true
    
    const url = form.url.split('#')[0]
    const pwd = form.pwd

    const response = await apiService.getShareInfo(url, pwd)
    if (!visible.value || form.url !== requestedUrl || form.name !== requestedName || form.pwd !== pwd) return
    
    if (response.success && response.folder_name) {
      const filename = response.folder_name
      
      // This function only runs on an explicit button click.
      form.name = filename
      
      // 如果开启了路径和名称同步，更新保存路径
      if (pathNameSync.value && form.name) {
        const basePath = getDefaultSavePath.value || ''
        // 修复路径拼接问题，避免出现//
        const cleanBasePath = basePath.replace(/\/+$/, '') // 移除末尾的所有斜杠
        form.save_dir = cleanBasePath ? `${cleanBasePath}/${form.name}` : `/${form.name}`
      }
    } else {
      ElMessage.warning(response.message || '未能获取分享信息，请检查提取码或稍后重试')
    }
  } catch (error) {
    ElMessage.warning('未能获取分享信息，请稍后重试')
    // 静默失败，不显示错误信息
    console.warn('URL解析失败:', error)
  } finally {
    isParsingUrl.value = false
  }
}

// 处理路径和名称同步
const handlePathNameSync = () => {
  if (!pathNameSync.value || !form.name) return
  
  const basePath = getDefaultSavePath.value || ''
  // 修复路径拼接问题，避免出现//
  const cleanBasePath = basePath.replace(/\/+$/, '') // 移除末尾的所有斜杠
  form.save_dir = cleanBasePath ? `${cleanBasePath}/${form.name}` : `/${form.name}`
}

// 自动补全搜索函数
const searchSavePaths = (queryString: string, callback: (suggestions: any[]) => void) => {
  const suggestions = taskSavePaths.value
    .filter(path => path.toLowerCase().includes(queryString.toLowerCase()))
    .map(path => ({ value: path }))
  callback(suggestions)
}

const searchCategories = (queryString: string, callback: (suggestions: any[]) => void) => {
  const suggestions = taskCategories.value
    .filter(category => category.toLowerCase().includes(queryString.toLowerCase()))
    .map(category => ({ value: category }))
  callback(suggestions)
}

const searchCronRules = (queryString: string, callback: (suggestions: any[]) => void) => {
  const commonCrons = [
    '*/5 * * * *',   // 每5分钟
    '0 * * * *',     // 每小时
    '0 0 * * *',     // 每天
    '0 0 * * 0',     // 每周
    '0 0 1 * *'      // 每月
  ]
  
  const allCrons = [...new Set([...commonCrons, ...taskCronRules.value])]
  const suggestions = allCrons
    .filter(cron => cron.toLowerCase().includes(queryString.toLowerCase()))
    .map(cron => ({ value: cron }))
  callback(suggestions)
}

const searchRegexPatterns = (queryString: string, callback: (suggestions: any[]) => void) => {
  const commonPatterns = [
    '^(\\d+)\\.mp4$',           // 数字命名的mp4文件
    '^.*\\.(mp4|mkv|avi)$',     // 视频文件
    '^.*\\.(jpg|png|gif)$',     // 图片文件
    '^.*\\.pdf$'                // PDF文件
  ]
  
  const allPatterns = [...new Set([...commonPatterns, ...taskRegexPatterns.value])]
  const suggestions = allPatterns
    .filter(pattern => pattern.toLowerCase().includes(queryString.toLowerCase()))
    .map(pattern => ({ value: pattern }))
  callback(suggestions)
}

const searchRegexReplaces = (queryString: string, callback: (suggestions: any[]) => void) => {
  const commonReplaces = [
    '第$1集.mp4',               // 第X集格式
    'S01E$1.mp4',              // 美剧格式
    '$1话.mp4'                 // 动漫格式
  ]
  
  const allReplaces = [...new Set([...commonReplaces, ...taskRegexReplaces.value])]
  const suggestions = allReplaces
    .filter(replace => replace.toLowerCase().includes(queryString.toLowerCase()))
    .map(replace => ({ value: replace }))
  callback(suggestions)
}

const loadTaskData = (task: Task) => {
  form.name = task.name || ''
  
  form.url = task.url
  const embedded = (() => { try { return new URL(task.url).searchParams.get('pwd') || '' } catch { return '' } })()
  form.pwd = task.pwd || embedded

  form.save_dir = task.save_dir
  form.category = task.category || ''
  form.cron = task.cron || ''
  form.regex_pattern = task.regex_pattern || ''
  form.regex_replace = task.regex_replace || ''
  form.media_type = task.media_type || 'other'
  form.flatten = task.flatten ?? false
  form.auto_rename = task.auto_rename ?? false
  form.season = task.season || 1
  form.force_first_season = task.force_first_season ?? false
  form.tmdb = task.tmdb ? { ...task.tmdb } : null
  form.season_folders = (task.season_folders || []).map(rule => ({ ...rule }))
  
  // 编辑任务时禁用同步开关，避免意外修改路径
  pathNameSync.value = false
  
  // 如果有高级设置数据，展开面板
  if (task.cron || task.regex_pattern || task.regex_replace) {
  }
}

// Cron助手功能
const showCronHelper = () => {
  ElMessage({
    type: 'info',
    duration: 5000,
    dangerouslyUseHTMLString: true,
    message: `
      <div style="text-align: left;">
        <strong>常用Cron表达式：</strong><br/>
        • */5 * * * * - 每5分钟<br/>
        • 0 */1 * * * - 每小时<br/>
        • 0 0 * * * - 每天0点<br/>
        • 0 0 */3 * * - 每3天0点<br/>
        • 0 0 * * 0 - 每周日0点
      </div>
    `
  })
}

const handleSubmit = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  if (form.auto_rename && !form.name.trim()) {
    ElMessage.warning('自动重命名需要填写自定义任务名称')
    return
  }

  submitting.value = true

  try {
    if (editingTask.value) {
      await taskStore.updateTask(editingTask.value.order - 1, form)
      ElMessage.success('任务已更新')
    } else {
      await taskStore.addTask(form)
      ElMessage.success('任务已添加')
    }

    visible.value = false
    resetForm()
    emit('success')
  } catch (error) {
    ElMessage.error(`操作失败: ${error}`)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  visible.value = false
  resetForm()
}

// 监听任务数据变化
watch(
  () => props.task,
  (newTask) => {
    // 使用nextTick确保DOM更新完成后再操作
    nextTick(() => {
      if (newTask) {
        loadTaskData(newTask)
      } else {
        // 强制重置表单，确保状态清空
        resetForm()
      }
    })
  },
  { immediate: true }
)

// 监听对话框显示状态
watch(visible, (newVisible) => {
  if (!newVisible) {
    resetForm()
  } else {
    // 对话框打开时，如果没有编辑任务，重置表单
    if (!props.task) {
      // 使用nextTick确保DOM更新完成后再重置
      nextTick(() => {
        resetForm()
      })
    }
  }
})

watch(() => form.url, (value) => {
  try {
    const code = new URL(value).searchParams.get('pwd')
    if (code !== null) form.pwd = code.trim()
  } catch { /* Leave the field intact while a URL is being typed. */ }
}, { flush: 'sync' })

// 监听任务名称变化，自动同步到保存路径
watch(() => form.media_type, (value) => {
  if (form.tmdb && form.tmdb.media_type !== value) form.tmdb = null
  if (value === 'other') form.auto_rename = false
  if (value !== 'tv') form.season_folders = []
})
watch(() => form.name, (newName) => {
  if (pathNameSync.value && newName) {
    handlePathNameSync()
  }
})

// 监听同步开关变化
watch(pathNameSync, (newValue) => {
  if (newValue && form.name) {
    handlePathNameSync()
  }
})
</script>

<style>
.add-task-dialog { max-width: calc(100vw - 24px); }
.add-task-dialog .el-dialog__body { max-height: min(68vh, calc(100dvh - 180px)); overflow-y: auto; padding: 16px 20px; }
.add-task-dialog .el-dialog__header { margin-right: 0; padding: 20px 20px 12px; border-bottom: 1px solid #ebeef5; }
.add-task-dialog .el-dialog__footer { padding: 12px 20px 16px; border-top: 1px solid #ebeef5; background: white; }
.add-task-dialog .el-form-item { margin-bottom: 20px; }
.add-task-dialog .el-form-item__label { white-space: nowrap; word-break: keep-all; font-weight: 500; }
.add-task-dialog .el-form-item__content { min-width: 0; align-items: flex-start; }
.add-task-dialog .form-help { flex-basis: 100%; width: 100%; margin-top: 6px; font-size: 12px; color: #73767a; line-height: 1.6; overflow-wrap: anywhere; }
.add-task-dialog .link-actions { flex-basis: 100%; width: 100%; margin-top: 8px; }
.add-task-dialog .path-input-group, .add-task-dialog .cron-input-group { width: 100%; display: flex; align-items: center; gap: 10px; }
.add-task-dialog .path-select, .add-task-dialog .cron-select { flex: 1; min-width: 0; }
.add-task-dialog .dialog-footer { display: flex; justify-content: flex-end; gap: 12px; }
.add-task-dialog .season-rule { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
.add-task-dialog .season-rule > .el-input { flex: 1; min-width: 150px; }
@media (max-width: 640px) {
  .add-task-dialog { width: calc(100vw - 24px) !important; margin: 12px auto !important; }
  .add-task-dialog .el-form-item { display: block; }
  .add-task-dialog .el-form-item__label { display: block; width: auto !important; height: auto; padding: 0 0 6px; line-height: 1.5; text-align: left; }
  .add-task-dialog .el-form-item__content { margin-left: 0 !important; }
  .add-task-dialog .el-dialog__body { max-height: calc(100dvh - 160px); }
}
</style>
