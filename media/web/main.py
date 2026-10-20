import base64
import datetime
import os.path
import re
import shutil
import sqlite3
import time
import traceback
import urllib
import xml.dom.minidom
from functools import wraps
from math import floor
from pathlib import Path
from threading import Lock
from urllib import parse

from flask import Flask, request, json, render_template, make_response, session, send_from_directory, send_file
from flask_compress import Compress
from flask_login import LoginManager, login_user, login_required, current_user

import log
from app.brushtask import BrushTask
from app.conf import ModuleConf, SystemConfig
from app.downloader import Downloader
from app.filter import Filter
from app.helper import SecurityHelper, MetaHelper, ChromeHelper, ThreadHelper
from app.indexer import Indexer
from app.media.meta import MetaInfo
from app.mediaserver import WebhookEvent
from app.message import Message
from app.rsschecker import RssChecker
from app.sites import Sites
from app.speedlimiter import SpeedLimiter
from app.subscribe import Subscribe
from app.sync import Sync
from app.torrentremover import TorrentRemover
from app.utils import DomUtils, SystemUtils, ExceptionUtils, StringUtils
from app.utils.types import *
from config import PT_TRANSFER_INTERVAL, Config
from web.action import WebAction
from web.apiv1 import apiv1_bp
from web.backend.WXBizMsgCrypt3 import WXBizMsgCrypt
from web.backend.user import User
from web.backend.wallpaper import get_login_wallpaper
from web.backend.web_utils import WebUtils
from web.security import require_auth

# 配置文件锁
ConfigLock = Lock()

# Flask App
App = Flask(__name__)
App.config['JSON_AS_ASCII'] = False
import media_profile
media_profile.install(App)
import hub_identity
hub_identity.configure_session(App)
App.permanent_session_lifetime = datetime.timedelta(days=30)

# 启用压缩
Compress(App)

# 登录管理模块
LoginManager = LoginManager()
LoginManager.login_view = "login"
LoginManager.init_app(App)
hub_identity.install(App, LoginManager)

# API注册
App.register_blueprint(apiv1_bp, url_prefix="/api/v1")


@App.after_request
def add_header(r):
    """
    统一添加Http头，标用缓存，避免Flask多线程+Chrome内核会发生的静态资源加载出错的问题
    r.headers["Cache-Control"] = "no-cache, no-store, max-age=0"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    """
    return r


# 定义获取登录用户的方法
@LoginManager.user_loader
def load_user(user_id):
    return User().get(user_id)


# 页面不存在
@App.errorhandler(404)
def page_not_found(error):
    return render_template("404.html", error=error), 404


# 服务错误
@App.errorhandler(500)
def page_server_error(error):
    return render_template("500.html", error=error), 500


def action_login_check(func):
    """
    Action安全认证
    """

    @wraps(func)
    def login_check(*args, **kwargs):
        if not current_user.is_authenticated:
            return {"code": -1, "msg": "用户未登录"}
        return func(*args, **kwargs)

    return login_check


# 主页面
@App.route('/', methods=['GET', 'POST'])
def login():
    def redirect_to_navigation(userinfo):
        """
        跳转到导航页面
        """
        # 判断当前的运营环境
        SystemFlag = SystemUtils.get_system()
        SyncMod = Config().get_config('pt').get('rmt_mode')
        TMDBFlag = 1 if Config().get_config('app').get('rmt_tmdbkey') else 0
        if not SyncMod:
            SyncMod = "link"
        RmtModeDict = WebAction().get_rmt_modes()
        RestypeDict = ModuleConf.TORRENT_SEARCH_PARAMS.get("restype")
        PixDict = ModuleConf.TORRENT_SEARCH_PARAMS.get("pix")
        SiteFavicons = {}
        Indexers = []
        SearchSource = "douban" if Config().get_config("laboratory").get("use_douban_titles") else "tmdb"
        CustomScriptCfg = SystemConfig().get_system_config("CustomScript")
        return render_template('navigation.html',
                               HubEmbedded=hub_identity.enabled(),
                               GoPage=GoPage if GoPage.split('?')[0] not in media_profile.REMOVED_PAGES else media_profile.landing_page(userinfo.pris),
                               UserName=userinfo.username,
                               UserPris=media_profile.permissions(userinfo.pris),
                               SystemFlag=SystemFlag.value,
                               TMDBFlag=TMDBFlag,
                               AppVersion=WebUtils.get_current_version(),
                               RestypeDict=RestypeDict,
                               PixDict=PixDict,
                               SyncMod=SyncMod,
                               SiteFavicons=SiteFavicons,
                               RmtModeDict=RmtModeDict,
                               Indexers=Indexers,
                               SearchSource=SearchSource,
                               CustomScriptCfg=CustomScriptCfg)

    def redirect_to_login(errmsg=''):
        """
        跳转到登录页面
        """
        return render_template('login.html',
                               GoPage=GoPage,
                               LoginWallpaper="",
                               err_msg=errmsg)

    if hub_identity.enabled():
        GoPage = request.args.get('next', 'mediafile').lstrip('/')
        return redirect_to_navigation(current_user)

    # 登录认证
    if request.method == 'GET':
        GoPage = request.args.get("next") or ""
        if GoPage.startswith('/'):
            GoPage = GoPage[1:]
        if current_user.is_authenticated:
            userid = current_user.id
            username = current_user.username
            if userid is None or username is None:
                return redirect_to_login()
            else:
                # 登录成功
                return redirect_to_navigation(User().get_user(username))
        else:
            return redirect_to_login()

    else:
        GoPage = request.form.get('next') or ""
        if GoPage.startswith('/'):
            GoPage = GoPage[1:]
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')
        if not username:
            return redirect_to_login('请输入用户名')
        user_info = User().get_user(username)
        if not user_info:
            return redirect_to_login('用户名或密码错误')
        # 校验密码
        if user_info.verify_password(password):
            # 创建用户 Session
            login_user(user_info)
            session.permanent = True if remember else False
            # 登录成功
            return redirect_to_navigation(user_info)
        else:
            return redirect_to_login('用户名或密码错误')


# 开始


# 资源搜索页面


# 电影订阅页面


# 电视剧订阅页面


# 订阅历史页面


# 订阅日历页面


# 站点维护页面


# 站点列表页面


# 站点资源页面


# 推荐页面


# 推荐页面


# 豆瓣电影


# 豆瓣电视剧






# Bangumi每日放送


# 媒体详情页面
@App.route('/media_detail', methods=['POST', 'GET'])
@login_required
def media_detail():
    TmdbId = request.args.get("id")
    Type = request.args.get("type")
    return render_template("discovery/mediainfo.html",
                           TmdbId=TmdbId,
                           Type=Type)


# 演职人员页面


# 正在下载页面


# 近期下载页面




# 数据统计页面


# 刷流任务页面


# 自定义下载器页面


# 服务页面
@App.route('/service', methods=['POST', 'GET'])
@login_required
def service():
    svg = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'
    cards = [
        ('sync', '目录同步', True), ('blacklist', '清理整理缓存', False),
        ('nametest', '名称识别测试', False),
        ('nettest', '网络连通性测试', False), ('backup', '备份&恢复', False)]
    tasks = [dict(id=id, name=name, state='ON' if enabled else 'OFF', time='', svg=svg, color='blue',
                  targets=ModuleConf.NETTEST_TARGETS if id == 'nettest' else {}) for id, name, enabled in cards]
    return render_template('service.html', Count=len(tasks), RuleGroups={}, SchedulerTasks=tasks)


# 历史记录页面
@App.route('/history', methods=['POST', 'GET'])
@login_required
def history():
    pagenum = request.args.get("pagenum")
    keyword = request.args.get("s") or ""
    current_page = request.args.get("page")
    Result = WebAction().get_transfer_history({"keyword": keyword, "page": current_page, "pagenum": pagenum})
    if Result.get("totalPage") <= 5:
        StartPage = 1
        EndPage = Result.get("totalPage")
    else:
        if Result.get("currentPage") <= 3:
            StartPage = 1
            EndPage = 5
        elif Result.get("currentPage") >= Result.get("totalPage") - 2:
            StartPage = Result.get("totalPage") - 4
            EndPage = Result.get("totalPage")
        else:
            StartPage = Result.get("currentPage") - 2
            if Result.get("totalPage") > Result.get("currentPage") + 2:
                EndPage = Result.get("currentPage") + 2
            else:
                EndPage = Result.get("totalPage")
    PageRange = range(StartPage, EndPage + 1)

    return render_template("rename/history.html",
                           TotalCount=Result.get("total"),
                           Count=len(Result.get("result")),
                           Historys=Result.get("result"),
                           Search=keyword,
                           CurrentPage=Result.get("currentPage"),
                           TotalPage=Result.get("totalPage"),
                           PageRange=PageRange,
                           PageNum=Result.get("currentPage"))


# TMDB缓存页面
@App.route('/tmdbcache', methods=['POST', 'GET'])
@login_required
def tmdbcache():
    page_num = request.args.get("pagenum")
    if not page_num:
        page_num = 30
    search_str = request.args.get("s")
    if not search_str:
        search_str = ""
    current_page = request.args.get("page")
    if not current_page:
        current_page = 1
    else:
        current_page = int(current_page)
    total_count, tmdb_caches = MetaHelper().dump_meta_data(search_str, current_page, page_num)

    total_page = floor(total_count / page_num) + 1

    if total_page <= 5:
        start_page = 1
        end_page = total_page
    else:
        if current_page <= 3:
            start_page = 1
            end_page = 5
        else:
            start_page = current_page - 3
            if total_page > current_page + 3:
                end_page = current_page + 3
            else:
                end_page = total_page

    page_range = range(start_page, end_page + 1)

    return render_template("rename/tmdbcache.html",
                           TotalCount=total_count,
                           Count=len(tmdb_caches),
                           TmdbCaches=tmdb_caches,
                           Search=search_str,
                           CurrentPage=current_page,
                           TotalPage=total_page,
                           PageRange=page_range,
                           PageNum=page_num)


# 手工识别页面
@App.route('/unidentification', methods=['POST', 'GET'])
@login_required
def unidentification():
    Items = WebAction().get_unknown_list().get("items")
    return render_template("rename/unidentification.html",
                           TotalCount=len(Items),
                           Items=Items)


# 文件管理页面
@App.route('/mediafile', methods=['POST', 'GET'])
@login_required
def mediafile():
    download_dirs = Downloader().get_download_visit_dirs()
    if download_dirs:
        try:
            DirD = os.path.commonpath(download_dirs).replace("\\", "/")
        except Exception as err:
            print(str(err))
            DirD = "/"
    else:
        DirD = "/"
    DirR = request.args.get("dir")
    return render_template("rename/mediafile.html",
                           Dir=DirR or DirD)


# 基础设置页面
@App.route('/basic', methods=['POST', 'GET'])
@login_required
def basic():
    proxy = Config().get_config('app').get("proxies", {}).get("http")
    if proxy:
        proxy = proxy.replace("http://", "")
    RmtModeDict = WebAction().get_rmt_modes()
    CustomScriptCfg = SystemConfig().get_system_config("CustomScript")
    return render_template("setting/basic.html",
                           Config=Config().get_config(),
                           Proxy=proxy,
                           RmtModeDict=RmtModeDict,
                           CustomScriptCfg=CustomScriptCfg)


# 自定义识别词设置页面
@App.route('/customwords', methods=['POST', 'GET'])
@login_required
def customwords():
    groups = WebAction().get_customwords().get("result")
    return render_template("setting/customwords.html",
                           Groups=groups,
                           GroupsCount=len(groups))


# 目录同步页面
@App.route('/directorysync', methods=['POST', 'GET'])
@login_required
def directorysync():
    RmtModeDict = WebAction().get_rmt_modes()
    SyncPaths = WebAction().get_directorysync().get("result")
    return render_template("setting/directorysync.html",
                           SyncPaths=SyncPaths,
                           SyncCount=len(SyncPaths),
                           RmtModeDict=RmtModeDict)


# 豆瓣页面


# 下载器页面


# 下载设置页面


# 索引器页面


# 媒体库页面
@App.route('/library', methods=['POST', 'GET'])
@login_required
def library():
    return render_template("setting/library.html", Config=Config().get_config())


# 媒体服务器页面
@App.route('/mediaserver', methods=['POST', 'GET'])
@login_required
def mediaserver():
    return render_template("setting/mediaserver.html",
                           Config=Config().get_config(),
                           MediaServerConf=ModuleConf.MEDIASERVER_CONF)


# 通知消息页面
@App.route('/notification', methods=['POST', 'GET'])
@login_required
def notification():
    MessageClients = Message().get_message_client_info()
    Channels = ModuleConf.MESSAGE_CONF.get("client")
    Switchs = {key: value for key, value in ModuleConf.MESSAGE_CONF.get("switch").items() if key in ("transfer_finished", "mediaserver_message")}
    MessageClients = {key: dict(value, switchs=[s for s in value.get("switchs", []) if s in Switchs]) for key, value in MessageClients.items()}
    return render_template("setting/notification.html",
                           Channels=Channels,
                           Switchs=Switchs,
                           ClientCount=len(MessageClients),
                           MessageClients=MessageClients)


# 字幕设置页面
@App.route('/subtitle', methods=['POST', 'GET'])
@login_required
def subtitle():
    ChromeOk = ChromeHelper().get_status()
    return render_template("setting/subtitle.html",
                           Config=Config().get_config(),
                           ChromeOk=ChromeOk)


# 用户管理页面
@App.route('/users', methods=['POST', 'GET'])
@login_required
def users():
    Users = WebAction().get_users().get("result")
    return render_template("setting/users.html", Users=Users, UserCount=len(Users))


# 过滤规则设置页面


# 自定义订阅页面


# RSS解析器页面


# 事件响应
@App.route('/do', methods=['POST'])
@action_login_check
def do():
    try:
        cmd = request.form.get("cmd")
        data = request.form.get("data")
    except Exception as e:
        ExceptionUtils.exception_traceback(e)
        return {"code": -1, "msg": str(e)}
    if data:
        data = json.loads(data)
    return WebAction().action(cmd, data)


# 目录事件响应
@App.route('/dirlist', methods=['POST'])
@login_required
def dirlist():
    from web.directory_listing import directory_html
    return make_response(directory_html(
        request.form.get('dir'),
        folders_only=request.form.get('filter') == 'HIDE_FILES_FILTER',
        show_parent=request.form.get('show_parent', '').lower() in ('true', '1'),
        refresh=request.form.get('refresh') == '1'), 200)


# 禁止搜索引擎
@App.route('/robots.txt', methods=['GET', 'POST'])
def robots():
    return send_from_directory("", "robots.txt")


# 响应企业微信消息
@App.route('/wechat', methods=['GET', 'POST'])
def wechat():
    # 当前在用的交互渠道
    interactive_client = Message().get_interactive_client(SearchType.WX)
    if not interactive_client:
        return make_response("NAStool没有启用微信交互", 200)
    conf = interactive_client.get("config")
    sToken = conf.get('token')
    sEncodingAESKey = conf.get('encodingAESKey')
    sCorpID = conf.get('corpid')
    if not sToken or not sEncodingAESKey or not sCorpID:
        return
    wxcpt = WXBizMsgCrypt(sToken, sEncodingAESKey, sCorpID)
    sVerifyMsgSig = request.args.get("msg_signature")
    sVerifyTimeStamp = request.args.get("timestamp")
    sVerifyNonce = request.args.get("nonce")

    if request.method == 'GET':
        if not sVerifyMsgSig and not sVerifyTimeStamp and not sVerifyNonce:
            return "NAStool微信交互服务正常！<br>微信回调配置步聚：<br>1、在微信企业应用接收消息设置页面生成Token和EncodingAESKey并填入设置->消息通知->微信对应项，打开微信交互开关。<br>2、保存并重启本工具，保存并重启本工具，保存并重启本工具。<br>3、在微信企业应用接收消息设置页面输入此地址：http(s)://IP:PORT/wechat（IP、PORT替换为本工具的外网访问地址及端口，需要有公网IP并做好端口转发，最好有域名）。"
        sVerifyEchoStr = request.args.get("echostr")
        log.debug("收到微信验证请求: echostr= %s" % sVerifyEchoStr)
        ret, sEchoStr = wxcpt.VerifyURL(sVerifyMsgSig, sVerifyTimeStamp, sVerifyNonce, sVerifyEchoStr)
        if ret != 0:
            log.error("微信请求验证失败 VerifyURL ret: %s" % str(ret))
        # 验证URL成功，将sEchoStr返回给企业号
        return sEchoStr
    else:
        try:
            sReqData = request.data
            log.debug("收到微信消息：%s" % str(sReqData))
            ret, sMsg = wxcpt.DecryptMsg(sReqData, sVerifyMsgSig, sVerifyTimeStamp, sVerifyNonce)
            if ret != 0:
                log.error("解密微信消息失败 DecryptMsg ret = %s" % str(ret))
                return make_response("ok", 200)
            # 解析XML报文
            """
            1、消息格式：
            <xml>
               <ToUserName><![CDATA[toUser]]></ToUserName>
               <FromUserName><![CDATA[fromUser]]></FromUserName> 
               <CreateTime>1348831860</CreateTime>
               <MsgType><![CDATA[text]]></MsgType>
               <Content><![CDATA[this is a test]]></Content>
               <MsgId>1234567890123456</MsgId>
               <AgentID>1</AgentID>
            </xml>
            2、事件格式：
            <xml>
                <ToUserName><![CDATA[toUser]]></ToUserName>
                <FromUserName><![CDATA[UserID]]></FromUserName>
                <CreateTime>1348831860</CreateTime>
                <MsgType><![CDATA[event]]></MsgType>
                <Event><![CDATA[subscribe]]></Event>
                <AgentID>1</AgentID>
            </xml>            
            """
            dom_tree = xml.dom.minidom.parseString(sMsg.decode('UTF-8'))
            root_node = dom_tree.documentElement
            # 消息类型
            msg_type = DomUtils.tag_value(root_node, "MsgType")
            # 用户ID
            user_id = DomUtils.tag_value(root_node, "FromUserName")
            # 没的消息类型和用户ID的消息不要
            if not msg_type or not user_id:
                log.info("收到微信心跳报文...")
                return make_response("ok", 200)
            # 解析消息内容
            content = ""
            if msg_type == "event":
                # 事件消息
                event_key = DomUtils.tag_value(root_node, "EventKey")
                if event_key:
                    log.info("点击菜单：%s" % event_key)
                    keys = event_key.split('#')
                    if len(keys) > 2:
                        content = ModuleConf.WECHAT_MENU.get(keys[2])
            elif msg_type == "text":
                # 文本消息
                content = DomUtils.tag_value(root_node, "Content", default="")
            if content:
                # 处理消息内容
                WebAction().handle_message_job(msg=content,
                                               in_from=SearchType.WX,
                                               user_id=user_id,
                                               user_name=user_id)
            return make_response(content, 200)
        except Exception as err:
            ExceptionUtils.exception_traceback(err)
            log.error("微信消息处理发生错误：%s - %s" % (str(err), traceback.format_exc()))
            return make_response("ok", 200)


# Plex Webhook
@App.route('/plex', methods=['POST'])
def plex_webhook():
    if not SecurityHelper().check_mediaserver_ip(request.remote_addr):
        log.warn(f"非法IP地址的媒体服务器消息通知：{request.remote_addr}")
        return '不允许的IP地址请求'
    request_json = json.loads(request.form.get('payload', {}))
    log.debug("收到Plex Webhook报文：%s" % str(request_json))
    ThreadHelper().start_thread(WebhookEvent().plex_action, (request_json,))
    ThreadHelper().start_thread(SpeedLimiter().plex_action, (request_json,))
    return 'Ok'


# Jellyfin Webhook
@App.route('/jellyfin', methods=['POST'])
def jellyfin_webhook():
    if not SecurityHelper().check_mediaserver_ip(request.remote_addr):
        log.warn(f"非法IP地址的媒体服务器消息通知：{request.remote_addr}")
        return '不允许的IP地址请求'
    request_json = request.get_json()
    log.debug("收到Jellyfin Webhook报文：%s" % str(request_json))
    ThreadHelper().start_thread(WebhookEvent().jellyfin_action, (request_json,))
    ThreadHelper().start_thread(SpeedLimiter().jellyfin_action, (request_json,))
    return 'Ok'


@App.route('/emby', methods=['POST'])
# Emby Webhook
def emby_webhook():
    if not SecurityHelper().check_mediaserver_ip(request.remote_addr):
        log.warn(f"非法IP地址的媒体服务器消息通知：{request.remote_addr}")
        return '不允许的IP地址请求'
    request_json = json.loads(request.form.get('data', {}))
    log.debug("收到Emby Webhook报文：%s" % str(request_json))
    ThreadHelper().start_thread(WebhookEvent().emby_action, (request_json,))
    ThreadHelper().start_thread(SpeedLimiter().emby_action, (request_json,))
    return 'Ok'


# Telegram消息响应
@App.route('/telegram', methods=['POST', 'GET'])
def telegram():
    """
    {
        'update_id': ,
        'message': {
            'message_id': ,
            'from': {
                'id': ,
                'is_bot': False,
                'first_name': '',
                'username': '',
                'language_code': 'zh-hans'
            },
            'chat': {
                'id': ,
                'first_name': '',
                'username': '',
                'type': 'private'
            },
            'date': ,
            'text': ''
        }
    }
    """
    # 当前在用的交互渠道
    interactive_client = Message().get_interactive_client(SearchType.TG)
    if not interactive_client:
        return 'NAStool未启用Telegram交互'
    msg_json = request.get_json()
    if not SecurityHelper().check_telegram_ip(request.remote_addr):
        log.error("收到来自 %s 的非法Telegram消息：%s" % (request.remote_addr, msg_json))
        return '不允许的IP地址请求'
    if msg_json:
        message = msg_json.get("message", {})
        text = message.get("text")
        user_id = message.get("from", {}).get("id")
        log.info("收到Telegram消息：from=%s, text=%s" % (user_id, text))
        # 获取用户名
        user_name = message.get("from", {}).get("username")
        if text:
            # 检查权限
            if text.startswith("/"):
                if str(user_id) not in interactive_client.get("client").get_admin():
                    Message().send_channel_msg(channel=SearchType.TG,
                                               title="只有管理员才有权限执行此命令",
                                               user_id=user_id)
                    return '只有管理员才有权限执行此命令'
            else:
                if not str(user_id) in interactive_client.get("client").get_users():
                    message.send_channel_msg(channel=SearchType.TG,
                                             title="你不在用户白名单中，无法使用此机器人",
                                             user_id=user_id)
                    return '你不在用户白名单中，无法使用此机器人'
            WebAction().handle_message_job(msg=text,
                                           in_from=SearchType.TG,
                                           user_id=user_id,
                                           user_name=user_name)
    return 'Ok'


# Synology Chat消息响应
@App.route('/synology', methods=['POST', 'GET'])
def synology():
    """
    token: bot token
    user_id
    username
    post_id
    timestamp
    text
    """
    # 当前在用的交互渠道
    interactive_client = Message().get_interactive_client(SearchType.SYNOLOGY)
    if not interactive_client:
        return 'NAStool未启用Synology Chat交互'
    msg_data = request.form
    if not SecurityHelper().check_synology_ip(request.remote_addr):
        log.error("收到来自 %s 的非法Synology Chat消息：%s" % (request.remote_addr, msg_data))
        return '不允许的IP地址请求'
    if msg_data:
        token = msg_data.get("token")
        if not interactive_client.get("client").check_token(token):
            log.error("收到来自 %s 的非法Synology Chat消息：token校验不通过！" % request.remote_addr)
            return 'token校验不通过'
        text = msg_data.get("text")
        user_id = int(msg_data.get("user_id"))
        log.info("收到Synology Chat消息：from=%s, text=%s" % (user_id, text))
        # 获取用户名
        user_name = msg_data.get("username")
        if text:
            WebAction().handle_message_job(msg=text,
                                           in_from=SearchType.SYNOLOGY,
                                           user_id=user_id,
                                           user_name=user_name)
    return 'Ok'


# Slack消息响应
@App.route('/slack', methods=['POST'])
def slack():
    """
    # 消息
    {
        'client_msg_id': '',
        'type': 'message',
        'text': 'hello',
        'user': '',
        'ts': '1670143568.444289',
        'blocks': [{
            'type': 'rich_text',
            'block_id': 'i2j+',
            'elements': [{
                'type': 'rich_text_section',
                'elements': [{
                    'type': 'text',
                    'text': 'hello'
                }]
            }]
        }],
        'team': '',
        'client': '',
        'event_ts': '1670143568.444289',
        'channel_type': 'im'
    }
    # 快捷方式
    {
      "type": "shortcut",
      "token": "XXXXXXXXXXXXX",
      "action_ts": "1581106241.371594",
      "team": {
        "id": "TXXXXXXXX",
        "domain": "shortcuts-test"
      },
      "user": {
        "id": "UXXXXXXXXX",
        "username": "aman",
        "team_id": "TXXXXXXXX"
      },
      "callback_id": "shortcut_create_task",
      "trigger_id": "944799105734.773906753841.38b5894552bdd4a780554ee59d1f3638"
    }
    # 按钮点击
    {
      "type": "block_actions",
      "team": {
        "id": "T9TK3CUKW",
        "domain": "example"
      },
      "user": {
        "id": "UA8RXUSPL",
        "username": "jtorrance",
        "team_id": "T9TK3CUKW"
      },
      "api_app_id": "AABA1ABCD",
      "token": "9s8d9as89d8as9d8as989",
      "container": {
        "type": "message_attachment",
        "message_ts": "1548261231.000200",
        "attachment_id": 1,
        "channel_id": "CBR2V3XEX",
        "is_ephemeral": false,
        "is_app_unfurl": false
      },
      "trigger_id": "12321423423.333649436676.d8c1bb837935619ccad0f624c448ffb3",
      "client": {
        "id": "CBR2V3XEX",
        "name": "review-updates"
      },
      "message": {
        "bot_id": "BAH5CA16Z",
        "type": "message",
        "text": "This content can't be displayed.",
        "user": "UAJ2RU415",
        "ts": "1548261231.000200",
        ...
      },
      "response_url": "https://hooks.slack.com/actions/AABA1ABCD/1232321423432/D09sSasdasdAS9091209",
      "actions": [
        {
          "action_id": "WaXA",
          "block_id": "=qXel",
          "text": {
            "type": "plain_text",
            "text": "View",
            "emoji": true
          },
          "value": "click_me_123",
          "type": "button",
          "action_ts": "1548426417.840180"
        }
      ]
    }
    """
    # 只有本地转发请求能访问
    if not SecurityHelper().check_slack_ip(request.remote_addr):
        log.warn(f"非法IP地址的Slack消息通知：{request.remote_addr}")
        return '不允许的IP地址请求'

    # 当前在用的交互渠道
    interactive_client = Message().get_interactive_client(SearchType.SLACK)
    if not interactive_client:
        return 'NAStool未启用Slack交互'
    msg_json = request.get_json()
    if msg_json:
        if msg_json.get("type") == "message":
            channel = msg_json.get("client")
            text = msg_json.get("text")
            username = ""
        elif msg_json.get("type") == "block_actions":
            channel = msg_json.get("client", {}).get("id")
            text = msg_json.get("actions")[0].get("value")
            username = msg_json.get("user", {}).get("name")
        elif msg_json.get("type") == "event_callback":
            channel = msg_json.get("event", {}).get("client")
            text = re.sub(r"<@[0-9A-Z]+>", "", msg_json.get("event", {}).get("text"), flags=re.IGNORECASE).strip()
            username = ""
        elif msg_json.get("type") == "shortcut":
            channel = ""
            text = msg_json.get("callback_id")
            username = msg_json.get("user", {}).get("username")
        else:
            return "Error"
        WebAction().handle_message_job(msg=text,
                                       in_from=SearchType.SLACK,
                                       user_id=channel,
                                       user_name=username)
    return "Ok"


# Jellyseerr Overseerr订阅接口


# 备份配置文件
@App.route('/backup', methods=['POST'])
@login_required
def backup():
    """
    备份用户设置文件
    :return: 备份文件.zip_file
    """
    try:
        # 创建备份文件夹
        config_path = Path(Config().get_config_path())
        backup_file = f"bk_{time.strftime('%Y%m%d%H%M%S')}"
        backup_path = config_path / "backup_file" / backup_file
        backup_path.mkdir(parents=True)
        # 把现有的相关文件进行copy备份
        shutil.copy(f'{config_path}/config.yaml', backup_path)
        shutil.copy(f'{config_path}/default-category.yaml', backup_path)
        shutil.copy(f'{config_path}/user.db', backup_path)
        conn = sqlite3.connect(f'{backup_path}/user.db')
        cursor = conn.cursor()
        # 执行操作删除不需要备份的表
        table_list = [
            'SEARCH_RESULT_INFO',
            'RSS_TORRENTS',
            'DOUBAN_MEDIAS',
            'TRANSFER_HISTORY',
            'TRANSFER_UNKNOWN',
            'TRANSFER_BLACKLIST',
            'SYNC_HISTORY',
            'DOWNLOAD_HISTORY',
            'alembic_version'
        ]
        for table in table_list:
            cursor.execute(f"""DROP TABLE IF EXISTS {table};""")
        conn.commit()
        cursor.close()
        conn.close()
        zip_file = str(backup_path) + '.zip'
        if os.path.exists(zip_file):
            zip_file = str(backup_path) + '.zip'
        shutil.make_archive(str(backup_path), 'zip', str(backup_path))
        shutil.rmtree(str(backup_path))
    except Exception as e:
        ExceptionUtils.exception_traceback(e)
        return make_response("创建备份失败", 400)
    return send_file(zip_file)


# 上传文件到服务器


# base64模板过滤器
@App.template_filter('b64encode')
def b64encode(s):
    return base64.b64encode(s.encode()).decode()


# split模板过滤器
@App.template_filter('split')
def split(string, char, pos):
    return string.split(char)[pos]


# 刷流规则过滤器
@App.template_filter('brush_rule_string')
def brush_rule_string(rules):
    return WebAction.parse_brush_rule_string(rules)


# 大小格式化过滤器
@App.template_filter('str_filesize')
def str_filesize(size):
    return StringUtils.str_filesize(size, pre=1)


# MD5 HASH过滤器
@App.template_filter('hash')
def md5_hash(text):
    return StringUtils.md5_hash(text)
