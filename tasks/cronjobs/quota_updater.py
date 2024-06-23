'''인스턴스 사용 할당량을 초기화하거나 업데이트하는 cronjob입니다.'''


import os
import sys
import logging
from datetime import datetime

import holidays
from pytz import timezone

from client.psql_client import PSQLClient


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.FileHandler('quota_updater.log', mode='a')]
)

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)


def is_midnight(dt: datetime) -> bool:
    '''현재 시간이 자정인지 확인합니다.'''

    if dt.hour == 0 and dt.minute == 0:
        return True

    return False


def get_todays_maxinum_quota(dt: datetime) -> int:
    '''오늘의 최대 인스턴스 사용 할당량을 시간으로 반환합니다.'''

    KR_HOLIDAYS = holidays.country_holidays(  # pylint: disable=invalid-name
        'KR', years=dt.year)

    if dt in KR_HOLIDAYS or dt.weekday() >= 5:
        return 12

    return 6


def main() -> None:
    '''인스턴스 사용 할당량을 초기화하거나 업데이트하는 작업을 수행하는 main 함수입니다.'''

    now_dt = datetime.now(timezone('Asia/Seoul'))

    # 인스턴스 사용량 초기화
    if is_midnight(now_dt):
        todays_maximum_quota = get_todays_maxinum_quota(now_dt)
        psql_client = PSQLClient()

        psql_client.reset_usage_quota(todays_maximum_quota)
        logging.info(
            '인스턴스 사용량 초기화 작업 진행 | %s | %d 시간',
            now_dt.strftime('%Y-%m-%d %H:%M:%S'),
            todays_maximum_quota
        )

        return None

    # 인스턴스 사용량 업데이트
    ...


if __name__ == '__main__':
    main()
