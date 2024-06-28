'''인스턴스 사용 할당량을 초기화 하거나 업데이트 하는 cronjob입니다.

이 작업은 18시 05분부터 익일 08시 30분까지 5분 단위로 수행됩니다.
'''


import os
import sys
import logging
from datetime import datetime, timedelta, time

import holidays
from pytz import timezone


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


def get_todays_maxinum_quota(dt: datetime) -> time:
    '''오늘의 최대 인스턴스 사용 할당량을 time 인스턴스로 반환합니다.'''

    KR_HOLIDAYS = holidays.country_holidays(  # pylint: disable=invalid-name
        'KR', years=dt.year)

    if dt in KR_HOLIDAYS or dt.weekday() >= 5:
        return time(hour=12)

    return time(hour=6)


def is_update_period(dt: datetime) -> bool:
    '''입력값으로 들어온 시간이 업데이트가 진행되는 시간인지 확인합니다.'''

    START_TIME = time(hour=18, minute=5)  # pylint: disable=invalid-name
    END_TIME = time(hour=8, minute=30)  # pylint: disable=invalid-name
    CURRENT_TIME = dt.time()  # pylint: disable=invalid-name

    if START_TIME <= CURRENT_TIME:
        return True

    if CURRENT_TIME <= END_TIME:
        return True

    return False


def get_user_data_model(
    cloudtrail_log: list[tuple[int, str, datetime]],
    today_maximum_quota: time
) -> dict[int, dict[str, list[tuple[str, datetime]] | time]]:
    '''사용자별 인스턴스 사용 데이터 모델을 생성합니다.'''

    user_data_model = {}

    for log in cloudtrail_log:
        iam_user_id, log_type, log_time = log

        if iam_user_id not in user_data_model:
            user_data_model[iam_user_id] = {
                'logs': [(log_type, log_time)],
                'usage_quota': today_maximum_quota
            }

            continue

        user_data_model[iam_user_id]['logs'].append((log_type, log_time))

    return user_data_model


def calculate_usage_per_period(
    start_time: datetime,
    stop_time: datetime,
    now_dt: datetime
) -> time:
    '''인스턴스 사용 주기에 따른 사용 시간을 계산합니다.'''

    KR_HOLIDAYS = holidays.country_holidays(  # pylint: disable=invalid-name
        'KR', years=now_dt.year)

    # 시간 보정
    if start_time.date() < now_dt.date():  # Case 1: 사용 주기가 전날 시작만 된 경우
        start_time = time.min  # 00시
    else:  # Case 2: 사용 주기가 오늘 시작되었고, 주기에 정규교육시간이 포함된 경우
        if now_dt.weekday() < 5 and now_dt not in KR_HOLIDAYS:
            if start_time.time() < time(8, 30):
                if stop_time.time() >= time(8, 30):  # Case 2-1: 정규교육시간 전에 켜서 이후에 끄는 경우
                    stop_time = stop_time.replace(hour=8, minute=30, second=0)
            else:  # elif start_time.time() >= time(8, 30):
                if start_time.time() < time(18, 0):
                    return time.min  # Case 2-2: 정규교육시간 내에 사용한 경우

    stop_time -= timedelta(hours=start_time.hour,
                           minutes=start_time.minute, seconds=start_time.second)

    return stop_time.time()


def update_usage_quota(
    user_data: dict[int, dict[str, list[tuple[str, datetime]] | time]],
    now_dt: datetime
) -> None:
    '''사용자별 인스턴스 사용 로그를 분석하여 잔여 할당량을 업데이트합니다.'''

    for data_instance in user_data.items():
        period_cnt = 0
        start_time = None
        usage_quota = data_instance[1]['usage_quota']  # Default hours

        for log in data_instance[1]['logs']:  # Each log
            log_type, log_time = log

            if log_type == 'StartInstances':
                period_cnt += 1
            elif log_type == 'StopInstances':
                if period_cnt == 0:
                    continue

                period_cnt -= 1

            if period_cnt >= 1:
                if period_cnt == 1:
                    if log_type != 'StopInstances':
                        start_time = log_time

                continue

            # 인스턴스 사용 주기에 확인 -> 시간 계산
            if log_time.date() < now_dt.date():  # 사용 주기가 전날 이루어진 경우
                continue

            usage_time = calculate_usage_per_period(
                start_time, log_time, now_dt)

            # 사용 시간 차감 및 잔여 할당량 계산
            usage_quota = datetime.combine(datetime.min, usage_quota)

            try:
                usage_quota -= timedelta(hours=usage_time.hour,
                                         minutes=usage_time.minute, seconds=usage_time.second)
                usage_quota = usage_quota.time()
            except OverflowError:  # 할당량이 음수가 되는 경우
                usage_quota = time.min

                break

        # 인스턴스 사용 주기가 없는 경우 (= 아직 사용을 중지하지 않은 사용자)
        if period_cnt >= 1:
            usage_time = calculate_usage_per_period(
                start_time, now_dt, now_dt)  # 현재시간 기준 계산

            # 사용 시간 차감 및 잔여 할당량 계산
            usage_quota = datetime.combine(datetime.min, usage_quota)

            try:
                usage_quota -= timedelta(hours=usage_time.hour,
                                         minutes=usage_time.minute, seconds=usage_time.second)
                usage_quota = usage_quota.time()
            except OverflowError:  # 할당량이 음수가 되는 경우 (= 할당량 초과)
                usage_quota = time.min

        data_instance[1]['usage_quota'] = usage_quota


def main() -> bool:
    '''인스턴스 사용 할당량을 초기화하거나 업데이트하는 작업을 수행하는 main 함수입니다.'''

    now_dt = datetime.now(timezone('Asia/Seoul'))
    todays_maximum_quota = get_todays_maxinum_quota(now_dt)
    psql_client = PSQLClient()  # pylint: disable=used-before-assignment
    KR_HOLIDAYS = holidays.country_holidays(  # pylint: disable=invalid-name
        'KR', years=now_dt.year)

    # 인스턴스 사용량 초기화
    if is_midnight(now_dt):
        psql_client.reset_usage_quota(todays_maximum_quota)
        logging.info(
            '인스턴스 사용량 초기화 작업 진행 | `now_dt`: %s | `todays_maximum_quota`: %s ',
            now_dt.strftime('%Y-%m-%d %H:%M:%S'),
            todays_maximum_quota
        )

        return True  # 초기화 작업 완료

    # 인스턴스 사용량 업데이트
    if not is_update_period(now_dt):
        if now_dt.weekday() < 5 and now_dt not in KR_HOLIDAYS:
            return False  # 평일 정규교육시간인 경우 사용량 업데이트 스킵

    # CloudTrail 로그 조회
    yesterday_dt = now_dt - timedelta(days=1)
    log_range_start_time = yesterday_dt.replace(
        hour=18, minute=0, second=0, microsecond=0)
    cloudtrail_log = psql_client.get_cloudtrail_log(
        range_start_time=log_range_start_time,
        range_end_time=now_dt)

    if not cloudtrail_log:
        logging.info(
            '조회된 CloudTrail 로그 데이터가 없음 | %s ~ %s',
            log_range_start_time.strftime('%Y-%m-%d %H:%M:%S'),
            now_dt.strftime('%Y-%m-%d %H:%M:%S')
        )

        return False

    # 사용자별 데이터 모델 생성
    user_data_model = get_user_data_model(
        cloudtrail_log,
        todays_maximum_quota
    )

    # 사용자별 인스턴스 사용량 업데이트
    update_usage_quota(user_data_model, now_dt)

    # 업데이트된 사용량을 데이터베이스에 반영(적재)
    psql_client.update_ec2_usage_quota(user_data_model)
    logging.info(
        '사용자별 인스턴스 사용량 업데이트 작업 진행 | `now_dt`: %s | `todays_maximum_quota`: %s ',
        now_dt.strftime('%Y-%m-%d %H:%M:%S'),
        todays_maximum_quota
    )

    return True


if __name__ == '__main__':
    from client.psql_client import PSQLClient

    # 함수 실행 및 로깅
    if not main():
        logging.error('인스턴스 사용량 업데이트 작업 실패')
        sys.exit(1)

    logging.info('인스턴스 사용량 업데이트 작업 완료')
