import json
import logging
import time

from attr import attrs, attrib
from typing import Optional

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

logger = logging.getLogger(__name__)


@attrs
class RateLimitData(object):
    """
    ThisA class representing the rate limit data.
    Refer: https://developers.facebook.com/docs/graph-api/overview/rate-limiting#headers
    """
    call_count = attrib(default=0, type=int)
    total_cputime = attrib(default=0, type=int)
    total_time = attrib(default=0, type=int)
    type = attrib(default=None, type=Optional[str])
    estimated_time_to_regain_access = attrib(default=None, type=Optional[str])


def get_interval(usage_count):
    interval = 1
    if usage_count < 20:
        interval = 1
    elif usage_count < 50:
        interval = 3
    elif usage_count < 80:
        interval = 5
    elif usage_count < 90:
        interval = 60 * 5
        logging.debug("App usage is arrive {0}%, need sleep {1} seconds".format(usage_count, interval))
    elif usage_count < 100:
        interval = 60 * 10
        logging.debug("App usage is arrive {0}%, need sleep {1} seconds".format(usage_count, interval))
    elif usage_count > 100:
        interval = 60 * 20
        logging.debug("App usage is arrive {0}%, need sleep {1} seconds".format(usage_count, interval))

    return interval


class RateLimit(object):
    """
    app's rate limit message.
    Refer: https://developers.facebook.com/docs/graph-api/overview/rate-limiting#application-level-rate-limiting
    """
    DEFAULT_TIME_WINDOW = 60 * 60

    def __init__(self, rate_type="app"):
        self.__dict__["resources"] = {}
        self._type = rate_type

    @staticmethod
    def parse_headers(headers, key):
        usage = headers.get(key)
        if usage:
            try:
                data = json.loads(usage)
                return data
            except (TypeError, JSONDecodeError) as ex:
                logger.error("Exception in parse {0} data error. Usage is: {1}. errors: {2}".format(key, usage, ex))
                return None
        return None

    def set_limit(self, headers):
        app_usage = self.parse_headers(headers, "x-app-usage")
        if app_usage is not None:
            self.__dict__["resources"]["app"] = RateLimitData(**app_usage)

        business_usage = self.parse_headers(headers, "x-business-use-case-usage")
        if business_usage is not None:
            for business_id, items in business_usage.items():
                self.__dict__["resources"] = [RateLimitData(**item) for item in items]

    def get_sleep_interval(self):
        usage_count = max(
            self.call_count,
            self.total_time,
            self.total_cputime
        )
        return get_interval(usage_count)

    @property
    def info(self):
        return "Current Limit is RateLimit(call_count={0},total_cputime={1},total_time={2})".format(
            self.call_count, self.total_cputime, self.total_time
        )


class InstagramRateLimit(object):
    """
    Simple RateLimit check.
    Refer: https://developers.facebook.com/docs/graph-api/overview/rate-limiting#instagram-rate-limiting
    """
    DEFAULT_TIME_WINDOW = 60 * 60

    def __init__(self, **kwargs):
        self.type = 'instagram'
        self.call_count = kwargs.get('call_count', 0)
        self.total_cputime = kwargs.get('total_cputime', 0)
        self.total_time = kwargs.get('total_time', 0)
        self.reset_at = kwargs.get('reset_at', 0)

    def set_limit(self, headers, instagram_business_id):
        default_usage = {'call_count': 0, 'total_cputime': 0, 'total_time': 0, 'estimated_time_to_regain_access': 0}
        x_business_use_case_usage = headers.get('x-business-use-case-usage')
        if x_business_use_case_usage:
            try:
                usage_data = json.loads(x_business_use_case_usage)
                data = usage_data.get(instagram_business_id, [default_usage])[0]
            except (TypeError, JSONDecodeError):
                logging.debug("Can not get rate limit info for {0}. Usage: {1}".format(
                    instagram_business_id, x_business_use_case_usage
                ))
                data = default_usage
            self.call_count = data['call_count']
            self.total_cputime = data['total_cputime']
            self.total_time = data['total_time']
            now = int(time.time())
            self.reset_at = now + data['estimated_time_to_regain_access']

    def get_sleep_interval(self):
        now = int(time.time())
        if self.reset_at > now:
            need_sleep = self.reset_at - now
            logging.debug("Api call still limited. Maybe remain {} seconds".format(need_sleep))
            return need_sleep
        usage_count = max(
            self.call_count,
            self.total_time,
            self.total_cputime
        )
        return get_interval(usage_count)

    @property
    def info(self):
        return "Current Limit is RateLimit(call_count={0},total_cputime={1},total_time={2},reset_at={3})".format(
            self.call_count, self.total_cputime, self.total_time, self.reset_at
        )
