'''5분마다 AWS CloudTrail API를 호출하여 StopInstances, StartInstances, RunInstances 로그 정보를 수집하고 DB에 적재합니다.

데이터 누락 방지를 위해 로그 수집 시간 간격을 10분으로 설정하였습니다. 
'''


import os
import logging
import sys
from datetime import datetime, timedelta

import pytz


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('cloudtrail_log_pipeline.log', mode='a'),
    ],
)

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)


def parsing_ec2_logs(
    logs: list[dict]
) -> list[tuple[str, str, datetime]]:
    '''Log에서 EventName, EventTime, Instance ID 정보만 추출합니다.'''

    logs_list = []

    for log in logs:
        log_type = log.get('EventName')
        log_time = log.get('EventTime')

        for resource in log['Resources']:
            if resource['ResourceType'] == 'AWS::EC2::Instance':
                instance_id = resource['ResourceName']
                logs_list.append((instance_id, log_type, log_time))

    return logs_list


if __name__ == '__main__':
    from client.aws_client import CloudTrailClient
    from client.psql_client import PSQLClient

    cloudtrail_client = CloudTrailClient()
    psql_client = PSQLClient()
    end_time = datetime.now(pytz.utc)
    start_time = end_time - timedelta(minutes=10)
    logs_to_insert = []

    stop_logs = cloudtrail_client.get_event_log_by_event_name(
        'StopInstances',
        start_time,
        end_time
    )
    start_logs = cloudtrail_client.get_event_log_by_event_name(
        'StartInstances',
        start_time,
        end_time
    )
    run_logs = cloudtrail_client.get_event_log_by_event_name(
        'RunInstances',
        start_time,
        end_time
    )
    terminate_logs = cloudtrail_client.get_event_log_by_event_name(
        'TerminateInstances',
        start_time,
        end_time
    )

    if (stop_logs and start_logs and run_logs) is None:
        logging.error(
            'AWS CloudTrail의 이벤트 조회 실패로 cron 작업이 비정상 종료됩니다.'
        )
        sys.exit(1)

    total_logs = stop_logs + start_logs + run_logs + terminate_logs

    logs_to_insert_parsing = parsing_ec2_logs(total_logs)

    get_instance_in_db = psql_client.check_existed_instance_id()
    intance_id_in_db = [instance_id[0] for instance_id in get_instance_in_db]

    for log in logs_to_insert_parsing:
        instance_id = log[0]

        if instance_id in intance_id_in_db:
            logs_to_insert.append(log)


    if len(logs_to_insert) == 0:
        logging.info(
            'AWS CloudTrail Log Data 적재 실패 | `logs_to_insert`: %s', logs_to_insert)
        sys.exit(1)

    psql_client.insert_into_cloudtrail_log(logs_to_insert)
    logging.info('AWS CloudTrail Log Data 적재 성공')
