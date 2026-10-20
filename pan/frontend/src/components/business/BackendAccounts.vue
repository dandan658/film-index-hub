<template>
  <section class="backend-logins">
    <div class="backend-logins-heading">
      <div><h3>后台登录账号</h3><p class="form-tip">与百度网盘账号分开管理。所有登录账号拥有相同后台操作权限，共享任务、网盘配置和转存记忆。</p></div>
      <el-button type="primary" @click="open('create')">新增登录账号</el-button>
    </div>
    <p class="form-tip">原始账号保留并受保护，不能在此删除或重置密码。账号操作需要验证你当前登录账号的密码。</p>
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" />
    <div v-loading="loading" class="backend-logins-list">
      <div v-for="entry in accounts" :key="entry.username" class="backend-login-row">
        <div class="backend-login-name"><strong>{{ entry.username }}</strong><el-tag v-if="entry.is_primary" size="small">原始账号 · 受保护</el-tag><el-tag v-if="entry.is_current" type="success" size="small">当前登录</el-tag></div>
        <div class="backend-login-actions">
          <el-button v-if="!entry.is_primary" size="small" @click="open('reset', entry.username)">重置密码</el-button>
          <el-button v-if="!entry.is_primary" size="small" type="danger" plain :disabled="entry.is_current" @click="open('delete', entry.username)">{{ entry.is_current ? '当前账号不可删除' : '删除账号' }}</el-button>
        </div>
      </div>
      <el-empty v-if="!loading && !loadError && accounts.length === 0" description="暂无登录账号信息" :image-size="64" />
    </div>
    <el-button text :loading="loading" @click="loadAccounts">刷新账号列表</el-button>
    <el-dialog v-model="visible" :title="title" width="520px" :close-on-click-modal="false" :before-close="close" append-to-body @closed="clearPasswords">
      <p v-if="mode === 'delete'" class="backend-dialog-help">仅删除登录账号「{{ target }}」，不会删除共享任务、网盘账号或转存记忆。该账号已登录的会话将失效。</p>
      <p v-else class="backend-dialog-help">{{ mode === 'create' ? '新增账号可登录同一个后台，使用现有共享数据。' : '修改后，该账号其他已登录的会话将失效。' }}</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item v-if="mode === 'create'" label="新登录账号">
          <el-input v-model="form.username" maxlength="64" placeholder="输入新的后台登录账号" autocomplete="off" :disabled="saving" />
          <div class="form-tip">支持中文、字母、数字、下划线、点、@ 和短横线，区分大小写。</div>
        </el-form-item>
        <el-form-item v-else label="目标账号"><el-input :model-value="target" disabled /></el-form-item>
        <template v-if="mode !== 'delete'">
          <el-form-item label="新账号密码"><el-input v-model="form.password" type="password" show-password autocomplete="new-password" placeholder="至少 6 位" :disabled="saving" /></el-form-item>
          <el-form-item label="确认新密码"><el-input v-model="form.confirm" type="password" show-password autocomplete="new-password" :disabled="saving" /></el-form-item>
        </template>
        <el-form-item label="你当前登录账号的密码"><el-input v-model="form.currentPassword" type="password" show-password autocomplete="current-password" placeholder="验证本次账号管理操作" :disabled="saving" @keyup.enter="submit" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="close()">取消</el-button><el-button :type="mode === 'delete' ? 'danger' : 'primary'" :loading="saving" @click="submit">{{ mode === 'delete' ? '确认删除账号' : '保存账号' }}</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiService } from '@/services/api'
interface LoginAccount { username: string; is_primary: boolean; is_current: boolean }
const accounts = ref<LoginAccount[]>([])
const loading = ref(false), saving = ref(false), visible = ref(false), loadError = ref('')
const mode = ref<'create' | 'reset' | 'delete'>('create')
const target = ref('')
const form = reactive({ username: '', password: '', confirm: '', currentPassword: '' })
const title = computed(() => mode.value === 'create' ? '新增后台登录账号' : mode.value === 'reset' ? '重置登录密码' : '删除后台登录账号')
const clearPasswords = () => { form.password = ''; form.confirm = ''; form.currentPassword = '' }
const open = (action: 'create' | 'reset' | 'delete', username = '') => { mode.value = action; target.value = username; form.username = ''; clearPasswords(); visible.value = true }
const close = (done?: unknown) => { if (saving.value) return; visible.value = false; clearPasswords(); if (typeof done === 'function') done() }
const loadAccounts = async () => {
  loading.value = true; loadError.value = ''
  try {
    const response = await apiService.getLoginAccounts()
    if (!response.success) throw new Error(response.message || '无法获取登录账号')
    accounts.value = response.accounts || []
  } catch (error) { loadError.value = error instanceof Error ? error.message : '加载失败，请重试' }
  finally { loading.value = false }
}
const submit = async () => {
  if (saving.value) return
  if (!form.currentPassword) return ElMessage.warning('请输入当前登录账号的密码')
  if (mode.value === 'create' && !form.username.trim()) return ElMessage.warning('请输入新登录账号')
  if (mode.value !== 'delete' && (form.password.length < 6 || form.password !== form.confirm)) return ElMessage.warning('新密码至少 6 位，且两次输入需要一致')
  saving.value = true
  try {
    const current_password = form.currentPassword
    const response = mode.value === 'create'
      ? await apiService.addLoginAccount({ username: form.username.trim(), password: form.password, current_password })
      : mode.value === 'reset'
        ? await apiService.resetLoginPassword(target.value, { password: form.password, current_password })
        : await apiService.deleteLoginAccount(target.value, current_password)
    if (!response.success) throw new Error(response.message || '账号操作失败')
    ElMessage.success(response.message || '操作成功')
    visible.value = false; clearPasswords()
    await loadAccounts()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '账号操作失败') }
  finally { saving.value = false }
}
onMounted(loadAccounts)
</script>

<style scoped>
.backend-logins { margin-top:24px; min-width:0; }
.backend-logins-heading { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:12px; }
.backend-logins-heading h3 { margin-bottom:6px; }
.backend-logins-list { margin-top:16px; min-height:64px; }
.backend-login-row { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; padding:16px; margin-bottom:10px; border:1px solid var(--glass-separator); border-radius:16px; background:var(--inset-surface); }
.backend-login-name,.backend-login-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; min-width:0; }
.backend-login-name strong { overflow-wrap:anywhere; color:var(--text-primary); }
.backend-dialog-help { margin-bottom:18px; color:var(--text-secondary); line-height:1.6; }
.form-tip { color:var(--text-secondary); font-size:12px; line-height:1.6; margin-top:6px; width:100%; }
@media(max-width:640px) { .backend-logins-heading { flex-direction:column; } .backend-login-actions { width:100%; } }
</style>
