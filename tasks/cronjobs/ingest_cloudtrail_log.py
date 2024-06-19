'''5분마다 AWS CloudTrail에 적재된 StopInstances, StartInstances Log를 수집 및 DB에 적재합니다.'''


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
    total_logs = []

    stop_logs = cloudtrail_client.get_event_logs_by_event_names('StopInstances',
                                                                start_time, end_time)
    start_logs = cloudtrail_client.get_event_logs_by_event_names('StartInstances',
                                                                 start_time, end_time)

    cloudtrail_logs = stop_logs + start_logs

    for log in cloudtrail_logs:
        instance_id = log.get('Resources')[0].get('ResourceName')
        log_type = log.get('EventName')
        log_time = log.get('EventTime')

        total_logs.append((instance_id, log_type, log_time))

    psql_client.insert_into_cloudtrail_log(total_logs)
