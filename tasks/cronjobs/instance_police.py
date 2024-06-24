'''인스턴스 사용 할당량 초과 여부를 단속하는 모듈입니다.'''

import os
import logging
import sys


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

    # 할당 시간이 0 이 남은 iam_user_id를 추출 (ec2_usage_quota table)
    zero_quota_iam_user_ids = psql_client.get_iam_user_ids_with_no_remaining_time()

    if zero_quota_iam_user_ids is None:
        logging.error('DB 접근시 알수 없는 문제가 발생했습니다.')

    if len(zero_quota_iam_user_ids) == 0:
        logging.info('종료할 인스턴스가 존재하지 않아 정상 종료됩니다.')
        exit(0)

    iam_user_ids_list = []

    for iam_user_id in zero_quota_iam_user_ids:
        iam_user_ids_list.append(iam_user_id[0])

    # iam_user가 소유하고 있는 모든 인스턴스들 추출 (ownership_info table)
    zero_quota_instance_list = psql_client.get_instance_ids_for_owner(
        iam_user_ids_list
    )

    if zero_quota_instance_list is None:
        logging.error('DB 접근시 알 수 없는 문제가 발생했습니다.')

    # 지금 running 중인 instance만 추출
    running_instances = ec2_client.get_live_instance_id_list(['running'])

    stopped_instance_list = []
    iam_user_id_to_alarm = set()

    for instance in zero_quota_instance_list:
        if instance[0] in running_instances:
            stopped_instance_list.append(instance[0])
            iam_user_id_to_alarm.add(instance[1])

    # 모든 인스턴스들 중지
    if len(stopped_instance_list) == 0:
        logging.info('중지 할 인스턴스가 없어서 실행을 종료합니다.')
        exit(0)

    # if not ec2_client.stop_instance(stopped_instance_list):
    #     logging.error('인스턴스 중지 시, 알 수 없는 문제가 발생하여 실행을 종료합니다.')
    #     exit(1)

    # iam_user를 가진 slack_id 추출 (student table)
    slack_ids = psql_client.get_slack_id_by_iam_user_id(
        list(iam_user_id_to_alarm))

    if slack_ids is None:
        logging.error('DB 접근시 알 수 없는 문제가 발생했습니다.')

    for slack_id in slack_ids:
        slack_client.app.client.chat_postMessage(
            channel=slack_id[0],
            text='오늘의 사용시간이 만료되어 소유하고 있는 인스턴스가 자동 종료됩니다.'
        )
