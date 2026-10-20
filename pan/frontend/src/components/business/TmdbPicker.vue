<template>
  <section class="tmdb-picker">
    <div class="tmdb-search">
      <el-input v-model="query" placeholder="输入影片名称搜索 TMDB" clearable @keyup.enter="search" />
      <el-button :loading="loading" @click="search">搜索</el-button>
    </div>
    <div class="tmdb-tip">默认保存位置：{{ root }} → 选中后生成 {{ root.replace(/\/$/, '') }}/影片名称，并填入任务名称。已有路径仅在点击选中时修改。</div>
    <el-button text size="small" @click="settingsOpen = !settingsOpen">{{ configured ? 'TMDB 已配置 · 修改默认位置或凭据' : '配置 TMDB 凭据和默认保存位置' }}</el-button>
    <div v-if="settingsOpen" class="tmdb-settings">
      <label>百度网盘默认保存位置</label>
      <el-input v-model="rootDraft" placeholder="/001" />
      <label>API Key 或 API Read Access Token</label>
      <el-input v-model="tokenDraft" type="password" show-password autocomplete="off" :placeholder="configured ? '已配置，留空保留原凭据' : '从 TMDB 账户的 API 设置获取'" />
      <el-button :loading="saving" @click="saveSettings">保存 TMDB 配置</el-button>
    </div>
    <div v-if="selected" class="tmdb-selected">已选择：{{ selected.title }} {{ selected.year ? `(${selected.year})` : '' }} · TMDB {{ selected.id }} <el-button text size="small" @click="$emit('clear')">解除关联</el-button></div>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" />
    <div v-if="searched && !loading && !error && !results.length" class="tmdb-tip">没有找到影片，请换一个名称搜索。</div>
    <div class="tmdb-results">
      <article v-for="item in results" :key="item.id" class="tmdb-result">
        <div><strong>{{ item.title }}</strong> <span>{{ item.year }} · 评分 {{ item.vote_average }}</span></div>
        <div v-if="item.original_title !== item.title" class="tmdb-tip">{{ item.original_title }}</div>
        <p>{{ item.overview }}</p>
        <el-button size="small" type="primary" @click="$emit('select', item)">使用名称和保存目录</el-button>
      </article>
    </div>
    <div class="tmdb-tip">资料来源 TMDB。本产品使用 TMDB API，但未经 TMDB 认可或认证。</div>
  </section>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { apiService } from '@/services'
import { ElMessage } from 'element-plus'
const props = defineProps<{ mediaType: 'movie' | 'tv' | 'other'; name: string; selected?: any }>()
defineEmits<{ (e: 'select', item: any): void; (e: 'clear'): void }>()
const query = ref(props.name), root = ref('/001'), rootDraft = ref('/001'), tokenDraft = ref('')
const configured = ref(false), settingsOpen = ref(false), loading = ref(false), saving = ref(false), searched = ref(false), error = ref('')
const results = ref<any[]>([])
let searchRevision = 0
const message = (e: unknown) => e instanceof Error ? e.message : '请求失败，请稍后重试'
onMounted(async () => {
  try { const r = await apiService.getTmdbSettings(); root.value = rootDraft.value = r.settings.default_root; configured.value = r.settings.configured }
  catch (e) { error.value = message(e) }
})
watch(() => props.mediaType, () => { ++searchRevision; results.value = []; searched.value = false; loading.value = false; error.value = '' })
watch(() => props.name, name => { if (!query.value) query.value = name })
const saveSettings = async () => {
  if (saving.value) return
  ++searchRevision; loading.value = false
  saving.value = true
  try {
    const r = await apiService.saveTmdbSettings({ default_root: rootDraft.value, credential: tokenDraft.value })
    root.value = rootDraft.value = r.settings.default_root; configured.value = r.settings.configured
    tokenDraft.value = ''; settingsOpen.value = false; results.value = []; searched.value = false; error.value = ''
    ElMessage.success('TMDB 配置已保存')
  } catch (e) { error.value = message(e) }
  finally { saving.value = false }
}
const search = async () => {
  if (loading.value) return
  if (!query.value.trim()) query.value = props.name
  if (!query.value.trim()) { error.value = '请输入影片名称'; return }
  const revision = ++searchRevision
  loading.value = true; error.value = ''; results.value = []; searched.value = true
  try {
    const r = await apiService.searchTmdb(query.value.trim(), props.mediaType)
    if (revision === searchRevision) results.value = r.results || []
  } catch (e) { if (revision === searchRevision) error.value = message(e) }
  finally { if (revision === searchRevision) loading.value = false }
}
</script>

<style scoped>
.tmdb-picker { width:100%; min-width:0; }
.tmdb-search { display:flex; gap:8px; }
.tmdb-search > .el-input { min-width:0; flex:1; }
.tmdb-tip { font-size:12px; color:var(--text-secondary); line-height:1.6; margin:8px 0; overflow-wrap:anywhere; }
.tmdb-settings { display:grid; gap:10px; padding:12px; border-radius:14px; background:var(--inset-surface); margin:8px 0; }
.tmdb-settings label { font-size:12px; }
.tmdb-selected { padding:10px; border-radius:12px; background:var(--inset-surface); margin:8px 0; overflow-wrap:anywhere; }
.tmdb-results { max-height:360px; overflow:auto; }
.tmdb-result { padding:12px; border:1px solid var(--glass-separator); border-radius:14px; margin-top:10px; overflow-wrap:anywhere; }
.tmdb-result span,.tmdb-result p { font-size:12px; line-height:1.6; color:var(--text-secondary); }
.tmdb-result p { margin:8px 0; white-space:pre-wrap; }
</style>
