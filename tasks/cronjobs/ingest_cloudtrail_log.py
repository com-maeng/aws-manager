'''5분마다 AWS CloudTrail API를 호출하여 StopInstances와 StartInstances 로그 정보를 수집하고 DB에 적재합니다.

이 스크립트는 cron 작업으로 5분마다 실행됩니다.
데이터 누락 방지를 위해 로그 수집 시간 간격을 10분으로 설정하였습니다. 
'''


import os
import sys
from datetime import datetime, timedelta

import pytz


current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.append(app_dir)


if __name__ == "__main__":
    from client.aws_client import CloudTrailClient
    from client.psql_client import PSQLClient

    cloudtrail_client = CloudTrailClient()
    psql_client = PSQLClient()
    end_time = datetime.now(pytz.utc)
    start_time = end_time - timedelta(minutes=10)
    logs_to_db = []

    stop_logs = cloudtrail_client.get_event_logs_by_event_name(
        'StopInstances',
        start_time,
        end_time
    )
    start_logs = cloudtrail_client.get_event_logs_by_event_name(
        'StartInstances',
        start_time,
        end_time
    )

    total_logs = stop_logs + start_logs

    for log in total_logs:
        instance_id = log.get('Resources')[0].get('ResourceName')
        log_type = log.get('EventName')
        log_time = log.get('EventTime')

        logs_to_db.append((instance_id, log_type, log_time))

    psql_client.insert_into_cloudtrail_log(logs_to_db)
