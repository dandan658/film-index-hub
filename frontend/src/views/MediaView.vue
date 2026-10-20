<template>
  <section class="hub-media-view">
    <div class="hub-media-toolbar"><span>媒体整理</span><el-select aria-label="媒体功能" v-model="selected" style="width:200px"><el-option v-for="item in mediaPages" :key="item.page" :value="item.page" :label="item.label" /></el-select><button type="button" @click="reload">刷新</button></div>
    <div v-if="!ready" class="hub-media-loading" role="status">正在打开媒体工作台…</div>
    <iframe ref="frame" :src="initialSource" title="媒体整理工作台" @load="onFrameLoad" />
  </section>
</template>
<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {mediaPages,validMediaPage} from '@/config/mediaPages'
const route=useRoute(), router=useRouter(), frame=ref<HTMLIFrameElement>(),ready=ref(false)
const selected=computed({get:()=>validMediaPage(route.query.page),set:page=>router.replace({path:'/media',query:{page}})})
const initialSource=ref('/media-engine/?next='+selected.value)
watch(selected,page=>{if(ready.value)frame.value?.contentWindow?.postMessage({type:'film-hub:navigate',page},location.origin);else initialSource.value='/media-engine/?next='+page})
const syncTheme=()=>frame.value?.contentWindow?.postMessage({type:'film-hub:theme',dark:false},location.origin)
const onFrameLoad=()=>{ready.value=true;syncTheme()}
const reload=()=>{ready.value=false;initialSource.value='/media-engine/?next='+selected.value+'&reload='+Date.now()}
</script>
<style scoped>
.hub-media-view{height:100%;min-height:420px;display:flex;flex-direction:column;position:relative}.hub-media-toolbar{display:flex;align-items:center;gap:12px;padding:10px 18px;color:var(--text-secondary)}.hub-media-toolbar select,.hub-media-toolbar button{font:inherit;border-radius:12px;border:1px solid var(--glass-border);background:var(--glass-panel);color:var(--text-primary);padding:8px 12px}.hub-media-view iframe{width:100%;flex:1;border:0;min-height:360px;border-radius:22px;background:transparent}.hub-media-loading{position:absolute;top:100px;left:0;right:0;text-align:center;color:var(--text-secondary)}@media(max-width:767px){.hub-media-toolbar{padding:8px 12px;gap:8px}.hub-media-toolbar>span{display:none}.hub-media-toolbar select{flex:1;min-width:0}}
</style>
