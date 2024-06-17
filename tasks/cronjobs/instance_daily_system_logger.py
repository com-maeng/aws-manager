'''사용 시간 계산을 위해 적절한 시간에 시스템 로그를 기록하는 기능을 구현합니다.

자정에 실행 중인 인스턴스들에 대해 시작 로그(start log)를 기록합니다.
오전 8시 30분에 실행 중인 인스턴스들에 대해 종료 로그(stop log)를 기록합니다.
'''


import os
import sys
from datetime import datetime
from pytz import timezone

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)

if __name__ == "__main__":
    from client.instance_usage_manager import InstanceUsageManager
    from client.aws_client import EC2Client
    from client.psql_client import PSQLClient

    ec2_client = EC2Client()
    psql_client = PSQLClient()
    instance_usage_manager = InstanceUsageManager()
    running_instance = ec2_client.get_live_instance_id_list(['running'])

    today_dt = datetime.now(timezone('Asia/Seoul'))

    if today_dt.hour == 0:
        for instance_id in running_instance:
            psql_client.insert_system_logs(instance_id, 'start', str(
                instance_usage_manager.midnight_time))

    elif today_dt.hour == 8:
        for instance_id in running_instance:
            psql_client.insert_system_logs(instance_id, 'stop', str(
                instance_usage_manager.midnight_time))
