// 版本管理配置
export const VERSION_CONFIG = {
  APP_VERSION: __APP_VERSION__,
  BUILD_TIME: __BUILD_TIME__,
  RELEASE_NOTES: '全站液态玻璃视觉；重构登录页；统一表单、弹窗和日志；适配明暗外观与移动设备',
  UPDATE_NOTES: {
    'v1.7.0': '全站液态玻璃视觉与重构登录页；明暗外观、自适应表单及动效优化',
    'v1.6.0': 'TMDB 搜索影片资料并生成保存目录；支持整个订阅统一第一季开关',
    'v1.5.0': '新增后台登录账号管理；保留原账号密码、任务和转存记忆；新增密码哈希及会话撤销',
    'v1.4.1': '修复多季订阅被命名为第一季；识别带剧名的中文、英文季目录；保留分享根目录季数',
    'v1.4.0': '统一玻璃视觉与交互动画；适配手机、平板和宽屏；修复导航数量标记错位',
    'v1.3.0': '移动文件后不重复转存；删除任务清除记忆；优化监控交互和后台并发；修复提取码和表单布局',
    'v1.2.0': '自定义任务名；合并或保留子目录；独立分季命名；修复正则捕获组重命名',
    'v1.1.5': '版本号改为从 package.json 自动注入',
    'v1.1.3': '前端重构版本 - Vue 3 + TypeScript',
    'v1.1.2': '优化轮询机制',
    'v1.1.1': '优化界面响应速度'
  }
} as const

export const APP_VERSION = VERSION_CONFIG.APP_VERSION
export const BUILD_TIME = VERSION_CONFIG.BUILD_TIME
export const RELEASE_NOTES = VERSION_CONFIG.RELEASE_NOTES
