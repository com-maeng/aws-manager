''' 최근 1시간 사이에 생성된 인스턴스의 소유자 정보를 추출하여 데이터베이스에 적재하는 기능을 제공합니다. 

30분마다 cron 작업을 통해 실행되며, 기존에 저장되어 있던 인스턴스 정보와 비교하여 중복되지 않은 소유자 정보만 적재합니다. 
'''


import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)


if __name__ == "__main__":
    import pytz
    from datetime import datetime, timedelta

    from client.aws_client import CloudTrailClient
    from client.psql_client import PSQLClient

    cloudtrail_client = CloudTrailClient()
    psql_client = PSQLClient()

    end_time = datetime.now(pytz.utc)
    start_time = end_time - timedelta(hours=1)

    runinstance_event_list = cloudtrail_client.get_event_logs_by_event_name(
        'RunInstances', start_time, end_time)
    owner_info = cloudtrail_client.get_instance_owner_info(
        runinstance_event_list)

    new_instance_id = [info[1] for info in owner_info]
    exist_instance_id = psql_client.check_existed_instance_id(
        new_instance_id)
    final_onwer_info = list(set(owner_info) - set(exist_instance_id))

    if final_onwer_info:
        psql_client.insert_into_ownership(final_onwer_info)
