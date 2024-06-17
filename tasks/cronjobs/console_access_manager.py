'''교육생의 콘솔 접근 권한을 자동으로 관리하는 cronjob입니다.

교육생들에게 기존에 부여되었던 IAM Policy를 회수하거나 부여함으로써 콘솔 접근 권한을 관리합니다.
정규교육이 시작/종료되는 시간에 맞춰 평일 오전 8시 30분과 오후 6시에 실행됩니다.
공휴일과 같이 정규교육이 진행되지 않는 날에는 관리 작업이 수행되지 않습니다.
'''


import os
import sys
import logging
from datetime import datetime

import holidays
from pytz import timezone


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('console_access_manager.log', mode='a'),
    ],
)

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)


def is_regular_education_day(today_dt: datetime) -> bool:
    '''정규교육이 진행되는 날인지 확인합니다.'''

    kr_holidays = holidays.country_holidays('KR', years=today_dt.year)

    if today_dt in kr_holidays:
        return False

    return True


def main() -> None:
    '''메인 로직이 실행되는 함수입니다.'''

    STUDENT_GROUP_NAME = 'student'  # pylint: disable=invalid-name
    STUDENT_POLICY_ARN = 'arn:aws:iam::473952381102:policy/GeneralStudentsPolicy'  # pylint: disable=invalid-name

    today_dt = datetime.now(timezone('Asia/Seoul'))

    if not is_regular_education_day(today_dt):
        logging.info('비정규교육일 | %s', today_dt)
        sys.exit(0)

    iam_client = IAMClient()  # pylint: disable=used-before-assignment

    if today_dt.hour == 8:
        iam_client.attach_policy_to_group(
            group_name=STUDENT_GROUP_NAME,
            policy_arn=STUDENT_POLICY_ARN,
        )
        logging.info('교육생 콘솔 접근 권한(정책) 부여 완료 | %s', today_dt)
    elif today_dt.hour == 18:
        iam_client.detach_policy_from_group(
            group_name=STUDENT_GROUP_NAME,
            policy_arn=STUDENT_POLICY_ARN,
        )
        logging.info('교육생 콘솔 접근 권한(정책) 제거 완료 | %s', today_dt)


if __name__ == '__main__':
    from client.aws_client import IAMClient

    main()
