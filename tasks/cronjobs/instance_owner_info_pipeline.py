''' 최근 1시간 사이에 생성된 인스턴스의 소유자 정보를 추출하여 데이터베이스에 적재하는 기능을 제공합니다. 

30분마다 cron 작업을 통해 실행되며, 기존에 저장되어 있던 인스턴스 정보와 비교하여 중복되지 않은 소유자 정보만 적재합니다. 
'''


import os
import logging
import sys


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('instance_owner_info_pipeline.log', mode='a'),
    ],
)

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)


def ec2_run_log_parser(
    runinstance_events: list[dict]
) -> list[tuple[str, str]]:
    '''Log들 중 instance id와 instance의 소유권 정보를 추출'''

    owner_info_list = []

    for event in runinstance_events:
        user_name = event['Username']
        for resource in event['Resources']:
            if resource['ResourceType'] == 'AWS::EC2::Instance':
                ec2_instance_id = resource['ResourceName']
                owner_info_list.append((user_name, ec2_instance_id))

    return owner_info_list


if __name__ == "__main__":
    from datetime import datetime, timedelta

    import pytz

    from client.aws_client import CloudTrailClient
    from client.psql_client import PSQLClient

    cloudtrail_client = CloudTrailClient()
    psql_client = PSQLClient()

    end_time = datetime.now(pytz.utc)
    start_time = end_time - timedelta(hours=1)
    owner_logs_to_insert = []

    run_logs = cloudtrail_client.get_event_log_by_event_name(
        'RunInstances',
        start_time,
        end_time
    )

    if run_logs is None:
        logging.error(
            'AWS CloudTrail의 이벤트 조회 실패로 cron 작업이 비정상 종료됩니다. | %s ',
            run_logs
        )
        sys.exit(1)

    if len(run_logs) == 0:
        logging.info(
            'AWS CloudTrail의 새로운 RunInstances Events가 없으므로 정상 종료됩니다.'
        )
        sys.exit(0)

    instance_owned_info = ec2_run_log_parser(run_logs)
    iam_user_info_from_db = dict(
        psql_client.get_iam_user()
    )  # {user_name : user_id}

    for info in instance_owned_info:
        iam_name, instance_id = info
        owned_by = iam_user_info_from_db.get(iam_name)

        if owned_by:
            owner_logs_to_insert.append((owned_by, instance_id))

    if len(owner_logs_to_insert) != 0:
        psql_client.insert_into_ownership_info(owner_logs_to_insert)
        logging.info(
            '인스턴스 소유 데이터 적재 성공 | %s',
            owner_logs_to_insert
        )
