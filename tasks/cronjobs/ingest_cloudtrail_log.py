'''5분마다 AWS CloudTrail API를 호출하여 StopInstances와 StartInstances 로그 정보를 수집하고 DB에 적재합니다.

이 스크립트는 cron 작업으로 5분마다 실행됩니다.
데이터 누락 방지를 위해 로그 수집 시간 간격을 10분으로 설정하였습니다. 
'''


import os
import logging
import sys
from datetime import datetime, timedelta

import pytz


current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)


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

    if not (stop_logs and start_logs):
        logging.error(
            'AWS CloudTrail의 이벤트 조회 실패로 cron 작업이 비정상 종료됩니다. | %s | %s',
            start_logs,
            stop_logs
        )
        sys.exit(1)

    total_logs = stop_logs + start_logs

    for log in total_logs:
        instance_id = log.get('Resources')[0].get('ResourceName')
        log_type = log.get('EventName')
        log_time = log.get('EventTime')

        logs_to_insert.append((instance_id, log_type, log_time))

    if logs_to_insert:
        psql_client.insert_into_cloudtrail_log(logs_to_insert)
        logging.info(
            'AWS CloudTrail Log Data 적재 성공 | %s',
            logs_to_insert
        )