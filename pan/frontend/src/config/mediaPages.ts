export const mediaPages = [
  {page:'mediafile',label:'文件管理'}, {page:'unidentification',label:'手动识别'},
  {page:'history',label:'整理历史'}, {page:'tmdbcache',label:'TMDB 缓存'},
  {page:'service',label:'整理服务'}, {page:'basic',label:'媒体基础设置'},
  {page:'library',label:'媒体库'}, {page:'directorysync',label:'目录同步'},
  {page:'notification',label:'媒体通知'}, {page:'customwords',label:'自定义识别词'},
  {page:'mediaserver',label:'媒体服务器'}, {page:'subtitle',label:'字幕'}
] as const
export const validMediaPage = (value: unknown) => mediaPages.some(p => p.page === value) ? String(value) : 'mediafile'
