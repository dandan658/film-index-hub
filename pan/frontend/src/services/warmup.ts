let scheduled=false
export function warmupCommonViews(){
  if(scheduled)return;scheduled=true
  const nav=navigator as Navigator & {deviceMemory?:number;connection?:{saveData?:boolean}}
  if(nav.connection?.saveData || (nav.deviceMemory && nav.deviceMemory<=2))return
  const warm=()=>{if(document.hidden)return;void import('@/views/tasks/TasksView.vue');void import('@/views/MediaView.vue')
    for(const href of ['/static/css/tabler.min.css','/static/css/liquid-glass.css','/static/js/jquery-3.3.1.min.js','/static/js/tabler.min.js']){const link=document.createElement('link');link.rel='prefetch';link.href=href;document.head.append(link)}
  }
  if('requestIdleCallback' in window)window.requestIdleCallback(warm,{timeout:5000});else setTimeout(warm,2500)
}
