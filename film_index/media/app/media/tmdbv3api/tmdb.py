# -*- coding: utf-8 -*-

import ast
import re
from contextvars import ContextVar
import logging
import os
import time
from functools import lru_cache

import requests
import requests.exceptions

from .as_obj import AsObj
from .exceptions import TMDbException

logger = logging.getLogger(__name__)
LAST_TMDB_ERROR = ContextVar("last_tmdb_error", default="")


class TMDb(object):
    TMDB_API_KEY = "TMDB_API_KEY"
    TMDB_LANGUAGE = "TMDB_LANGUAGE"
    TMDB_WAIT_ON_RATE_LIMIT = "TMDB_WAIT_ON_RATE_LIMIT"
    TMDB_DEBUG_ENABLED = "TMDB_DEBUG_ENABLED"
    TMDB_CACHE_ENABLED = "TMDB_CACHE_ENABLED"
    TMDB_PROXIES = "TMDB_PROXIES"
    TMDB_DOMAIN = "TMDB_DOMAIN"
    REQUEST_CACHE_MAXSIZE = 256

    def __init__(self, obj_cached=True, session=None):
        self._session = requests.Session() if session is None else session
        self._remaining = 40
        self._reset = None
        self.obj_cached = obj_cached
        if os.environ.get(self.TMDB_LANGUAGE) is None:
            os.environ[self.TMDB_LANGUAGE] = "zh-CN"
        if not os.environ.get(self.TMDB_DOMAIN):
            os.environ[self.TMDB_DOMAIN] = "https://api.themoviedb.org/3"

    @property
    def page(self):
        return os.environ["page"]

    @property
    def total_results(self):
        return os.environ["total_results"]

    @property
    def total_pages(self):
        return os.environ["total_pages"]

    @property
    def api_key(self):
        return os.environ.get(self.TMDB_API_KEY)

    @property
    def domain(self):
        return os.environ.get(self.TMDB_DOMAIN)

    @domain.setter
    def domain(self, domain):
        if domain:
            if not str(domain).startswith('http'):
                domain = "https://%s" % domain
            if not str(domain).endswith('/3'):
                domain = "%s/3" % domain
            os.environ[self.TMDB_DOMAIN] = str(domain)
        else:
            os.environ[self.TMDB_DOMAIN] = ''

    @property
    def proxies(self):
        return os.environ.get(self.TMDB_PROXIES)

    @proxies.setter
    def proxies(self, proxies):
        os.environ[self.TMDB_PROXIES] = 'None'
        if proxies:
            proxies_strs = []
            for key, value in proxies.items():
                if not value:
                    continue
                proxies_strs.append("'%s': '%s'" % (key, value))
            if proxies_strs:
                os.environ[self.TMDB_PROXIES] = "{%s}" % ",".join(proxies_strs)
            else:
                os.environ[self.TMDB_PROXIES] = 'None'

    @api_key.setter
    def api_key(self, api_key):
        os.environ[self.TMDB_API_KEY] = str(api_key)

    @property
    def language(self):
        return os.environ.get(self.TMDB_LANGUAGE)

    @language.setter
    def language(self, language):
        os.environ[self.TMDB_LANGUAGE] = language

    @property
    def wait_on_rate_limit(self):
        if os.environ.get(self.TMDB_WAIT_ON_RATE_LIMIT) == "False":
            return False
        else:
            return True

    @wait_on_rate_limit.setter
    def wait_on_rate_limit(self, wait_on_rate_limit):
        os.environ[self.TMDB_WAIT_ON_RATE_LIMIT] = str(wait_on_rate_limit)

    @property
    def debug(self):
        if os.environ.get(self.TMDB_DEBUG_ENABLED) == "True":
            return True
        else:
            return False

    @debug.setter
    def debug(self, debug):
        os.environ[self.TMDB_DEBUG_ENABLED] = str(debug)

    @property
    def cache(self):
        if os.environ.get(self.TMDB_CACHE_ENABLED) == "False":
            return False
        else:
            return True

    @cache.setter
    def cache(self, cache):
        os.environ[self.TMDB_CACHE_ENABLED] = str(cache)

    @staticmethod
    def _get_obj(result, key="results", all_details=False):
        if "success" in result and result["success"] is False:
            raise TMDbException(result["status_message"])
        if all_details is True or key is None:
            return AsObj(**result)
        else:
            return [AsObj(**res) for res in result[key]]

    @staticmethod
    @lru_cache(maxsize=REQUEST_CACHE_MAXSIZE)
    def cached_request(method, url, data, proxies, authorization=None):
        response = requests.request(method, url, data=data, proxies=TMDb.parse_proxies(proxies), headers={'Authorization': authorization} if authorization else {}, verify=False, timeout=10)
        TMDb.check_response(response)
        return response

    @staticmethod
    def parse_proxies(value):
        if not value or value == 'None':
            return None
        parsed = ast.literal_eval(value)
        if parsed is not None and (not isinstance(parsed, dict) or any(key not in ('http', 'https') or not isinstance(url, str) for key, url in parsed.items())):
            raise TMDbException('代理配置格式错误，请在媒体基础设置中检查代理服务器')
        return parsed

    @staticmethod
    def check_response(response):
        code = response.status_code
        if code in (401, 403): message = 'TMDB 凭据无效或无访问权限，请检查媒体或订阅 TMDB 配置'
        elif code == 429: message = 'TMDB 请求过于频繁，请稍后重试'
        elif code >= 400: message = f'TMDB 服务请求失败（HTTP {code}）'
        else: return
        LAST_TMDB_ERROR.set(message)
        raise TMDbException(message)

    def cache_clear(self):
        return self.cached_request.cache_clear()

    def _call(
            self, action, append_to_response, call_cached=True, method="GET", data=None
    ):
        if self.api_key is None or self.api_key == "":
            raise TMDbException("No API key found.")

        token = self.api_key.removeprefix('Bearer ').strip()
        is_key = re.fullmatch(r'[0-9a-fA-F]{32}', token) is not None
        authorization = None if is_key else 'Bearer ' + token
        query = ('api_key=' + token + '&') if is_key else ''
        # Image language is optional: a text locale must not hide neutral stills.
        language_query = '' if action.endswith('/images') else '&language=' + self.language
        url = "%s%s?%s%s%s" % (self.domain, action, query, append_to_response, language_query)
        try:
            if self.cache and self.obj_cached and call_cached and method != "POST":
                req = self.cached_request(method, url, data, self.proxies, authorization)
            else:
                req = self._session.request(method, url, data=data, proxies=self.parse_proxies(self.proxies), headers={'Authorization': authorization} if authorization else {}, timeout=10, verify=False)
                self.check_response(req)
        except (requests.RequestException, ValueError, SyntaxError, TypeError):
            message = '无法连接 TMDB 或代理配置无效，请检查 NAS 网络和媒体代理设置'
            LAST_TMDB_ERROR.set(message)
            raise TMDbException(message) from None

        headers = req.headers

        if "X-RateLimit-Remaining" in headers:
            self._remaining = int(headers["X-RateLimit-Remaining"])

        if "X-RateLimit-Reset" in headers:
            self._reset = int(headers["X-RateLimit-Reset"])

        if self._remaining < 1:
            current_time = int(time.time())
            sleep_time = self._reset - current_time

            if self.wait_on_rate_limit:
                logger.warning("Rate limit reached. Sleeping for: %d" % sleep_time)
                time.sleep(abs(sleep_time))
                return self._call(action, append_to_response, call_cached, method, data)
            else:
                raise TMDbException(
                    "Rate limit reached. Try again in %d seconds." % sleep_time
                )

        try:
            json = req.json()
        except ValueError:
            message = 'TMDB 返回了非 JSON 数据，请检查代理地址或网络拦截'
            LAST_TMDB_ERROR.set(message)
            raise TMDbException(message) from None

        if "page" in json:
            os.environ["page"] = str(json["page"])

        if "total_results" in json:
            os.environ["total_results"] = str(json["total_results"])

        if "total_pages" in json:
            os.environ["total_pages"] = str(json["total_pages"])

        if self.debug:
            logger.info(json)
            logger.info(self.cached_request.cache_info())

        if "errors" in json:
            raise TMDbException(json["errors"])

        return json
