# Film Index Hub · 订阅与媒体整理工作台

把百度网盘订阅和 Film Index 媒体整理合在一个 Compose 项目中：一个地址、一次登录、一套导航。统一登录沿用百度订阅的后台账号，包括原有新增登录账号。继续提供液态玻璃界面及原创影视 Logo，不包含 PT、下载器、索引器或做种功能。

## 飞牛部署与保留原数据

1. 在飞牛 Docker / Compose 中**停止原百度订阅和 Film Index 两个项目**，保留其目录和文件。
2. 新建独立目录，下载本仓库的 `compose.yaml` 和 `.env.example`，把 `.env.example` 另存为 `.env`。
3. 在 `.env` 设置以下真实宿主机目录：

```dotenv
PAN_CONFIG_DIR=/原百度订阅的配置目录
PAN_LOG_DIR=/原百度订阅的日志目录
MEDIA_CONFIG_DIR=/原FilmIndex的配置目录
MEDIA_ROOT=/原FilmIndex映射的媒体父目录
PAN_MEMORY=384m
MEDIA_MEMORY=384m
```

`PAN_CONFIG_DIR` 必须是实际含 `config.json` 的文件夹，而非项目父目录；该目录通常也含 `.session-secret`。`MEDIA_CONFIG_DIR` 必须是含 `config.yaml` 和原数据库的目录；`MEDIA_ROOT` 沿用原来映射到 `/media` 的同一宿主路径，避免已有同步目录失效。不同旧 YAML 可能使用 `./config` 或 `./data/config`，请看旧项目实际挂载，不要凭文件夹名称推测。

4. 飞牛新建 Compose 项目 `film-index-hub`，使用 `compose.yaml`，点击拉取并启动。
5. 打开 `http://NAS的IP:18520`，使用**原百度订阅后台账号密码**。首次切换到合并版需要重新登录一次，此后无需再次登录媒体模块。
6. 左侧“百度订阅 / 网盘账号 / 系统设置”处理网盘任务；“媒体整理”内包含文件管理、识别、历史、目录同步、媒体库、字幕等功能。手机底部“媒体”也能进入，并可在页面顶部选择功能。

如果原本有账号任务，却在新日志看到 `Initial admin password` 且任务为空，说明连接到了空配置目录；停止新项目并修正 `PAN_CONFIG_DIR`，不要覆盖原 `config.json`。部署不主动删除账号、任务、转存记忆、媒体配置或整理历史。不要把同一数据目录同时交给新旧两个运行实例。

全新安装可保持默认目录。百度后台会首次生成管理员密码，显示在 pan 服务日志中。百度网盘自身 Cookie 与后台账号是两件事：原配置中有效的网盘登录 Cookie 会保留，过期后仍需重新添加。

## 更新

```sh
docker compose pull
docker compose up -d
```

三个镜像的 `latest` 在通过整套测试后才发布。更新保持 `.env`、原配置映射和 `./data/hub` 不变。不要用旧的单项目 YAML 拉取合并版镜像。

## 低占用与流畅交互

- 一个轻量网关对外开放 18520；两个引擎不向宿主机单独开放端口，隔离依赖及故障。
- 媒体引擎改用单进程 WSGI、4 请求线程和 4 调度线程，取消 PM2 和启动时虚拟显示/浏览器进程；网盘引擎限制为 8 请求线程。
- 默认内存上限为网盘 384MiB、媒体 384MiB、网关 64MiB。这是限制值，**不是实际空闲占用**。低于上限的实际用量取决于任务、目录数量和第三方服务；可按 NAS 内存调整 `.env`。
- 拆分原来约 1.1MB 的前端大包，按页面导入。登录后仅在空闲且非省流量/低内存设备上预热常用模块；不全盘扫描、不预载视频或全部海报。
- 媒体工作台首次打开时加载，之后切换功能只更新内容区；编辑器仅在基础设置中按需加载。
- 路径菜单异步读取、8 秒短缓存、大目录筛选、独立玻璃浮层；标签页隐藏后不再进行任务状态轮询。
- 唯一后台 Cookie 使用独立名字并保存签名密钥，避免 NAS 相同 IP 的不同端口服务互相覆盖。

## 本地源码构建

```sh
python3 scripts/source_bundle.py
docker compose -f compose.yaml -f compose.build.yaml build
docker compose -f compose.yaml -f compose.build.yaml up -d
```

当前支持 linux/amd64（x86-64 NAS）。`pan/` 基于已修改的百度订阅 v1.7，`media/` 基于已精简的 Film Index v1.2；各自原始许可和说明保留，整合代码按 AGPL-3.0 提供。源码包通过网关 `/project-source.zip` 下载，不包含挂载数据、真实配置或 `.env`。

## 验证范围

发布前检查统一认证、拒绝伪造身份、原登录账号、重启后的会话保留、退出后的媒体权限撤销、全部媒体页面，以及已有网盘任务和媒体整理回归测试。CI 保存容器空闲占用与进程清单作为证据；这不是你的 NAS 实测。真实百度 Cookie、云盘挂载、媒体移动和外部 TMDB/字幕服务仍需在 NAS 验证。

发布 v2.0.0 已通过[整套容器验证](https://github.com/dandan658/film-index-hub/actions/runs/39387604322)，测试镜像源码提交为 `e9113ff949525a77f929cc603cda965693b265dc`。包括 67 项网盘回归、12 个媒体页面、原会话重启保留、第二个后台账号登录和退出权限撤销。测试机启动并完成登录/重启测试后的内存采样：网盘 41.84MiB、媒体 93.17MiB、网关 3.523MiB，合计约 139MiB；媒体进程只有 `python3 hub_server.py`。这是空配置测试样本，实际 NAS 负载需部署后观察。

界面更新 v2.0.1：统一固定为白色半透明玻璃，包括登录页、弹窗和媒体工作台，不跟随系统切换深色。
