'''인스턴스 사용 할당량 초과 여부를 단속하는 모듈입니다.'''

import os
import logging
import sys


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


if __name__ == "__main__":
    from client.instance_usage_manager import InstanceUsageManager
    from client.aws_client import EC2Client
    from client.psql_client import PSQLClient
    from client.slack_client import SlackClient

    instance_usage_manager = InstanceUsageManager()
    ec2_client = EC2Client()
    psql_client = PSQLClient()
    slack_client = SlackClient()

    zero_quota_infos = psql_client.get_slack_id_and_instance_id_with_no_remaining_time()

    if zero_quota_infos is None:
        logging.error('DB 접근시 알수 없는 문제가 발생했습니다.')
        sys.exit(1)

    if len(zero_quota_infos) == 0:
        logging.info('종료할 인스턴스가 존재하지 않아 정상 종료됩니다.')
        sys.exit(0)

    running_instances = ec2_client.get_live_instance_id_list(['running'])
    stopped_instance_list = []
    slack_id_to_alarm = set()

    for info in zero_quota_infos:
        instance_id = info[1]
        slack_id = info[0]

        if instance_id in running_instances:
            stopped_instance_list.append(instance_id)
            slack_id_to_alarm.add(slack_id)

    if len(stopped_instance_list) == 0:
        logging.info('중지 할 인스턴스가 없어서 실행을 종료합니다.')
        sys.exit(0)

    if not ec2_client.stop_instance(stopped_instance_list):
        logging.error('인스턴스 중지 시, 알 수 없는 문제가 발생하여 실행을 종료합니다.')
        sys.exit(1)

    for slack_id in slack_id_to_alarm:
        slack_client.app.client.chat_postMessage(
            channel=slack_id,
            text='오늘의 EC2 사용시간이 만료되어 소유하고 있는 모든 인스턴스가 자동 종료됩니다.'
        )
