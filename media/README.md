# Film and Television Index · 液态玻璃版

纯媒体整理工具，基于 NAStools v2.9.1。源码：https://github.com/dandan658/film-and-television-index

## 保留功能

- 媒体整理：文件管理、手动识别、历史记录、TMDB 缓存。
- 服务：目录同步、清理整理缓存、名称识别测试、网络测试、备份恢复。
- 设置：基础设置、用户管理、媒体库、目录同步、消息通知、自定义识别词、媒体服务器、字幕。

已下架所有 PT 获取和做种功能：站点、探索、资源搜索、索引器、下载器、下载设置、订阅、豆瓣订阅、刷流、删种、种子上传、下载过滤规则及其 API、操作命令和定时任务。旧配置中的 PT 开关不会重新启用这些功能。消息通知只保留媒体整理及媒体服务器事件。底层文件整理仍复用上游公共模块，因此代码中的历史配置键 `pt.rmt_mode` 表示文件整理方式，保留以兼容原配置。

## NAS 直接拉取

适用 x86-64 NAS，镜像：`ghcr.io/dandan658/film-and-television-index:latest`。

1. 下载 `compose.nas.yaml`，在飞牛 Docker / Compose 中新建独立项目。
2. 将 `${MEDIA_ROOT:-./media}:/media` 中的宿主目录改为真实媒体父目录；应用内统一使用 `/media` 路径。
3. 启动后访问 `http://NAS的IP:18510`。全新配置账号 `admin`，密码 `password`。
4. 设置 TMDB、媒体库和目录同步。把待整理目录和媒体库的共同父目录映射为 `/media`，有利于硬链接正常工作。

更新时拉取最新镜像并重建，保留已有配置目录映射：

```sh
docker compose -f compose.nas.yaml pull
docker compose -f compose.nas.yaml up -d
```

`pull_policy: always` 只在部署/重建时检查更新。不要改变现有配置映射；`./config` 与 `./data/config` 是不同目录，必须沿用部署时的路径。不要把同一配置目录同时挂载给两个运行中的实例。旧账号、媒体配置、整理历史沿用上游格式，不主动删除。底层自动升级已关闭，避免覆盖定制版本。

## v1.2.0 界面与性能

独立门户浮层修复目录菜单层级遮挡，目录读取异步显示状态，8 秒缓存和手动刷新减少重复扫描；后端使用 `os.scandir` 减少逐文件属性查询。超时后可重试或手动输入完整路径。大目录每次最多渲染 200 项，可搜索其余条目。原生单选下拉框统一玻璃菜单，保留原字段值和 change 事件。取消嵌套全屏模糊，并移除已下架功能的大型图表和日历脚本。使用原创 SVG 影视 Logo，左下角仅显示版本。

## 本地构建与验证

完整源码目录中执行 `docker compose build && docker compose up -d`。`compose.yaml` 用于本地构建，`compose.nas.yaml` 用于直接拉取。

GitHub Actions 执行 13 项测试、导航和脚本语法检查，然后构建 amd64 镜像，验证容器启动、默认账号登录、全部 13 个保留页面和源码包下载，通过后发布 latest。真实 NAS 目录同步、整理、第三方服务连接及挂载性能仍需在你的环境验证。

## 源码与许可

原版权与 AGPL-3.0 许可保留于 `LICENSE.md`，本修改版沿用此许可。固定基础镜像和上游提交见 `UPSTREAM.json`，第三方依赖引用见 `THIRD_PARTY.lock.json`。源码公开于本仓库，运行界面账户菜单也提供 `/project-source.zip` 下载；不包含挂载配置、媒体及 `.env`。原项目说明见 `README_UPSTREAM.md`。
