'''매 시간 마다 생성된 인스턴스의 소유자 정보를 추출하고 적재하는 기능.'''


import os
import sys


current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)


if __name__ == "__main__":
    from datetime import datetime, timedelta
    import pytz
    from client.aws_client import CloudTrailClient
    from client.psql_client import PSQLClient

    cloudtrail_client = CloudTrailClient()
    psql_client = PSQLClient()

    end_time = datetime.now(pytz.utc)
    start_time = end_time - timedelta(hours=1)

    runinstance_event_list = cloudtrail_client.get_runinstance_events(
        start_time, end_time)
    owner_info = cloudtrail_client.get_instance_owner_info(
        runinstance_event_list)

    new_instance_id = [info[1] for info in owner_info]
    exist_instance_id = psql_client.check_exisited_instance_id(
        new_instance_id)
    final_onwer_info = list(set(owner_info) - set(exist_instance_id))

    psql_client.insert_into_ownership(final_onwer_info)
