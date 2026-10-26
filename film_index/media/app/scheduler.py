import datetime
import math
import random
import traceback

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from film_index.media import log
from film_index.media.app.db import database_task
from film_index.media.app.helper import MetaHelper
from film_index.media.app.mediaserver import MediaServer
from film_index.media.app.sync import Sync
from film_index.media.app.utils import ExceptionUtils
from film_index.media.app.utils.commons import singleton
from film_index.media.config import PT_TRANSFER_INTERVAL, METAINFO_SAVE_INTERVAL, \
    SYNC_TRANSFER_INTERVAL, RSS_CHECK_INTERVAL, REFRESH_PT_DATA_INTERVAL, \
    RSS_REFRESH_TMDB_INTERVAL, META_DELETE_UNKNOWN_INTERVAL, REFRESH_WALLPAPER_INTERVAL, Config
from film_index.media.web.backend.wallpaper import get_login_wallpaper


@singleton
class Scheduler:
    SCHEDULER = None
    _pt = None
    _douban = None
    _media = None

    def __init__(self):
        self.init_config()

    def init_config(self):
        self._pt = Config().get_config('pt')
        self._media = Config().get_config('media')
        self._douban = Config().get_config('douban')

    def run_service(self):
        self.SCHEDULER = BackgroundScheduler(timezone=Config().get_timezone(), executors={'default': ThreadPoolExecutor(4)})
        sync_interval = (Config().get_config('sync') or {}).get('full_sync_interval')
        if sync_interval not in (None, ''):
            try:
                hours = float(sync_interval)
                if not math.isfinite(hours) or hours < 0 or hours > 168:
                    raise ValueError('out of range')
                if hours > 0:
                    self.SCHEDULER.add_job(database_task(self._run_directory_sync), 'interval',
                                           hours=hours, id='directory_full_sync',
                                           max_instances=1, coalesce=True)
                    log.info('【Sync】定时全量目录同步已启用，间隔 %s 小时' % hours)
            except (ValueError, TypeError):
                log.warn('定时目录同步周期无效，跳过该服务')
        if self._media and self._media.get('mediasync_interval'):
            try:
                hours = float(self._media['mediasync_interval'])
                if hours > 0: self.SCHEDULER.add_job(database_task(MediaServer().sync_mediaserver), 'interval', hours=hours)
            except (ValueError, TypeError):
                log.warn('媒体库同步周期无效，跳过该服务')
        self.SCHEDULER.add_job(database_task(MetaHelper().save_meta_data), 'interval', seconds=METAINFO_SAVE_INTERVAL)
        self.SCHEDULER.add_job(database_task(Sync().transfer_mon_files), 'interval', seconds=SYNC_TRANSFER_INTERVAL)
        self.SCHEDULER.add_job(database_task(MetaHelper().delete_unknown_meta), 'interval', hours=META_DELETE_UNKNOWN_INTERVAL)
        self.SCHEDULER.start()

    @staticmethod
    def _run_directory_sync():
        log.info('【Sync】定时目录同步任务开始')
        try:
            if Sync().transfer_all_sync():
                log.info('【Sync】定时目录同步任务结束')
            else:
                log.info('【Sync】已有目录同步正在运行，本次定时任务跳过')
        except Exception:
            log.error('【Sync】定时目录同步任务异常：%s' % traceback.format_exc())
            raise

    def stop_service(self):
        """
        停止定时服务
        """
        try:
            if self.SCHEDULER:
                self.SCHEDULER.remove_all_jobs()
                self.SCHEDULER.shutdown()
                self.SCHEDULER = None
        except Exception as e:
            ExceptionUtils.exception_traceback(e)

    def start_data_site_signin_job(self, hour, minute):
        year = datetime.datetime.now().year
        month = datetime.datetime.now().month
        day = datetime.datetime.now().day
        # 随机数从1秒开始，不在整点签到
        second = random.randint(1, 59)
        log.info("站点自动签到时间 即将在%s-%s-%s,%s:%s:%s签到" % (
            str(year), str(month), str(day), str(hour), str(minute), str(second)))
        if hour < 0 or hour > 24:
            hour = -1
        if minute < 0 or minute > 60:
            minute = -1
        if hour < 0 or minute < 0:
            log.warn("站点自动签到时间 配置格式错误：不启动任务")
            return
        self.SCHEDULER.add_job(Sites().signin,
                               "date",
                               run_date=datetime.datetime(year, month, day, hour, minute, second))


def run_scheduler():
    """
    启动定时服务
    """
    try:
        Scheduler().run_service()
    except Exception as err:
        log.error("启动定时服务失败：%s - %s" % (str(err), traceback.format_exc()))


def stop_scheduler():
    """
    停止定时服务
    """
    try:
        Scheduler().stop_service()
    except Exception as err:
        log.debug("停止定时服务失败：%s" % str(err))


def restart_scheduler():
    """
    重启定时服务
    """
    stop_scheduler()
    run_scheduler()
