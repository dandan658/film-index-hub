<template>
  <main class="liquid-login">
    <header class="login-brand"><img src="/favicon/favicon.svg" alt="" /><span>Film Index</span></header>
    <div class="login-stage">
      <section class="login-intro" aria-label="自动转存介绍">
        <span class="login-eyebrow"><i></i> 你的网盘，井然有序</span>
        <h1>让更新，<br />自动抵达。</h1>
        <p>订阅一次，持续追更。<br />把资源整理交给后台，把时间留给自己。</p>
        <div class="login-orbit" aria-hidden="true">
          <div class="orbit-ring"></div><div class="orbit-ring orbit-ring-inner"></div>
          <div class="orbit-core"><svg viewBox="0 0 48 48" fill="none"><path d="M15 33H12a8 8 0 0 1-1-16 13 13 0 0 1 25-1 9 9 0 0 1 1 18h-4M24 20v18m-7-7 7 7 7-7" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
          <div class="orbit-chip chip-subscribe"><b>↻</b><span>订阅更新<small>持续发现新内容</small></span></div>
          <div class="orbit-chip chip-organize"><b>✓</b><span>自动整理<small>每一份资源，各就其位</small></span></div>
        </div>
      </section>
      <section class="liquid-login-card" aria-labelledby="login-heading">
        <div class="login-card-mark"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="3" stroke="currentColor" stroke-width="1.6"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></div>
        <span class="login-eyebrow">欢迎回来</span><h2 id="login-heading">登录你的工作台</h2><p class="login-card-description">继续管理订阅与资源。</p>
        <form class="liquid-login-form" @submit.prevent="handleLogin">
          <label for="login-username">账号</label>
          <div class="liquid-login-field"><el-icon><User /></el-icon><input id="login-username" v-model="loginForm.username" name="username" autocomplete="username" placeholder="输入后台登录账号" :disabled="loading" required /></div>
          <label for="login-password">密码</label>
          <div class="liquid-login-field"><el-icon><Lock /></el-icon><input id="login-password" v-model="loginForm.password" name="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="输入登录密码" :disabled="loading" required /><button type="button" class="password-visibility" :aria-label="showPassword ? '隐藏密码' : '显示密码'" :aria-pressed="showPassword" :disabled="loading" @click="showPassword = !showPassword"><el-icon><Hide v-if="showPassword" /><View v-else /></el-icon></button></div>
          <p v-if="errorMessage" class="login-error" role="alert">{{ errorMessage }}</p>
          <button class="liquid-login-submit" type="submit" :disabled="loading"><span v-if="loading" class="login-spinner"></span><span>{{ loading ? '正在登录' : '进入工作台' }}</span><span v-if="!loading" aria-hidden="true">↗</span></button>
        </form>
        <div class="login-card-foot"><i></i> 使用原有后台账号或新增账号登录</div>
      </section>
    </div>
    <footer class="liquid-login-footer"><span>订阅 · 识别 · 整理</span><span>{{ APP_VERSION }}</span></footer>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { User, Lock, View, Hide } from '@element-plus/icons-vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { APP_VERSION } from '@/config/version'
const router = useRouter(), route = useRoute(), authStore = useAuthStore()
const loading = ref(false), showPassword = ref(false), errorMessage = ref('')
const loginForm = reactive({ username: '', password: '' })
const handleLogin = async () => {
  if (loading.value) return
  errorMessage.value = ''
  if (!loginForm.username.trim() || !loginForm.password) { errorMessage.value = '请输入账号和密码'; return }
  loading.value = true
  try {
    await authStore.login(loginForm.username, loginForm.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/')
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : '登录失败，请稍后重试' }
  finally { loading.value = false }
}
</script>

<style scoped>
.liquid-login { height:100dvh; overflow-y:auto; padding:32px clamp(24px,6vw,96px) 22px; display:flex; flex-direction:column; position:relative; isolation:isolate; }
.login-brand { display:flex; align-items:center; gap:12px; font-size:16px; font-weight:650; letter-spacing:-.4px; }.login-brand img { width:34px; height:34px; }
.login-stage { width:100%; max-width:1120px; margin:auto; display:grid; grid-template-columns:1.15fr 1fr; align-items:center; gap:clamp(48px,8vw,130px); padding:48px 0; }
.login-eyebrow { color:var(--text-secondary); display:inline-flex; align-items:center; gap:8px; font-size:12px; letter-spacing:1px; font-weight:600; }
.login-eyebrow i,.login-card-foot i { width:6px; height:6px; border-radius:50%; background:#159d88; display:inline-block; box-shadow:0 0 0 4px rgba(21,157,136,.09); flex-shrink:0; }
.login-intro h1 { font-size:clamp(48px,5.8vw,78px); line-height:1.16; letter-spacing:-4px; font-weight:740; margin:24px 0; }.login-intro > p { color:var(--text-secondary); font-size:16px; line-height:1.9; }
.login-orbit { width:330px; height:235px; margin-top:30px; position:relative; }.orbit-ring { width:232px; height:180px; border:1px solid var(--glass-border); border-radius:50%; position:absolute; left:36px; top:23px; transform:rotate(-25deg); box-shadow:inset 0 1px 1px rgba(255,255,255,.6),0 1px 1px rgba(48,103,137,.08); }.orbit-ring-inner { width:175px; height:230px; top:0; left:66px; transform:rotate(35deg); }
.orbit-core { width:94px; height:94px; border-radius:30px; color:var(--el-color-primary); display:grid; place-items:center; position:absolute; left:107px; top:65px; background:var(--liquid-surface); border:1px solid var(--glass-border); box-shadow:var(--liquid-shadow); transform:rotate(-9deg); }.orbit-core svg { width:48px; height:48px; }
.orbit-chip { position:absolute; display:flex; align-items:center; gap:12px; padding:13px 17px; border-radius:20px; background:var(--liquid-surface); border:1px solid var(--glass-border); box-shadow:var(--liquid-shadow); font-size:13px; font-weight:600; }.orbit-chip small { display:block; margin-top:3px; font-weight:400; font-size:10px; color:var(--text-secondary); }.chip-subscribe { left:0; top:6px; transform:rotate(-5deg); }.chip-organize { right:0; bottom:4px; transform:rotate(4deg); }.orbit-chip b { width:30px; height:30px; background:var(--accent-soft); display:grid; place-items:center; border-radius:10px; color:var(--el-color-primary); font-size:19px; }
.liquid-login-card { min-width:0; padding:38px; border-radius:36px; background:var(--liquid-surface); border:1px solid var(--glass-border); box-shadow:var(--liquid-shadow); position:relative; }.login-card-mark { width:48px; height:48px; border-radius:17px; background:var(--inset-surface); border:1px solid var(--glass-border); box-shadow:inset 0 1px 0 rgba(255,255,255,.7); display:grid; place-items:center; color:var(--el-color-primary); margin-bottom:24px; }.login-card-mark svg { width:24px; height:24px; }
.liquid-login-card h2 { font-size:27px; letter-spacing:-1px; line-height:1.4; margin:8px 0; }.login-card-description { color:var(--text-secondary); font-size:13px; }.liquid-login-form { margin-top:30px; }.liquid-login-form > label { display:block; font-size:12px; font-weight:600; margin-bottom:9px; }
.liquid-login-field { display:flex; align-items:center; gap:10px; border:1px solid var(--glass-border); border-radius:16px; background:var(--inset-surface); padding:0 14px; height:52px; margin-bottom:22px; box-shadow:inset 0 1px 3px rgba(30,74,108,.06),0 1px 0 rgba(255,255,255,.5); transition:box-shadow .2s ease; }.liquid-login-field:focus-within { box-shadow:0 0 0 3px var(--accent-soft); border-color:var(--el-color-primary); }.liquid-login-field > .el-icon { color:var(--text-secondary); flex-shrink:0; }
.liquid-login-field input { width:100%; min-width:0; height:100%; border:0; outline:none; background:transparent; color:var(--text-primary); font-size:16px; }.liquid-login-field input::placeholder { color:var(--text-secondary); opacity:.75; font-size:13px; }.password-visibility { display:grid; place-items:center; background:none; color:var(--text-secondary); border:0; width:32px; height:36px; flex-shrink:0; cursor:pointer; border-radius:10px; }
.liquid-login-submit { width:100%; height:52px; border-radius:17px; border:1px solid rgba(255,255,255,.4); background:linear-gradient(135deg,#087bf6,#0459d2); color:white; display:flex; justify-content:center; align-items:center; gap:12px; box-shadow:0 9px 20px -10px rgba(0,93,216,.65),inset 0 1px 1px rgba(255,255,255,.45); font-size:14px; font-weight:650; cursor:pointer; transition:transform .2s var(--ios-spring),box-shadow .2s ease; }.liquid-login-submit:hover { transform:translateY(-1px); }.liquid-login-submit:active { transform:scale(.98); }.liquid-login-submit:disabled { opacity:.6; cursor:wait; }
.login-error { color:var(--el-color-danger); font-size:12px; line-height:1.6; margin:-6px 0 16px; overflow-wrap:anywhere; }.login-spinner { width:16px; height:16px; border:2px solid rgba(255,255,255,.4); border-top-color:white; border-radius:50%; animation:login-spin .7s linear infinite; }.login-card-foot { display:flex; align-items:center; justify-content:center; gap:9px; color:var(--text-secondary); font-size:11px; margin-top:27px; line-height:1.6; }.liquid-login-footer { display:flex; justify-content:space-between; gap:12px; font-size:11px; color:var(--text-secondary); letter-spacing:.5px; padding-top:12px; }
@keyframes login-spin { to { transform:rotate(360deg); } }
@supports(backdrop-filter:blur(1px)) { .liquid-login-card { backdrop-filter:blur(24px) saturate(155%); -webkit-backdrop-filter:blur(24px) saturate(155%); }.orbit-chip,.orbit-core { backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px); } }
@media(max-width:820px) { .login-stage { grid-template-columns:1fr; max-width:460px; padding:30px 0; gap:28px; }.login-intro { display:none; }.liquid-login-card { padding:32px; }.liquid-login { padding:24px; }.login-brand { justify-content:center; }.liquid-login-footer { margin-top:12px; } }
@media(max-width:380px) { .liquid-login { padding:18px 14px; }.liquid-login-card { padding:26px 22px; border-radius:28px; }.liquid-login-card h2 { font-size:24px; }.login-card-foot { font-size:10px; } }
@media(prefers-reduced-transparency:reduce) { .liquid-login-card,.orbit-chip,.orbit-core { backdrop-filter:none; -webkit-backdrop-filter:none; } }
</style>
