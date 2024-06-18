'''인스턴스 사용 할당량 초과 여부를 단속하는 모듈입니다.'''

import os
import sys
from datetime import datetime, timedelta
from pytz import timezone


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

    stopped_instance_list = []
    running_instance = ec2_client.get_live_instance_id_list(['running'])

    for instance_id in running_instance:

        today_instance_logs = psql_client.get_today_instance_logs(instance_id)
        remaining_time = instance_usage_manager.get_remaining_time(
            today_instance_logs)
        slack_id = psql_client.get_slack_id_by_instance(instance_id)

        if remaining_time <= timedelta():
            ec2_client.stop_instance(instance_id)
            psql_client.insert_system_logs(instance_id, 'stop', str(
                datetime.now(timezone('Asia/Seoul'))))
            stopped_instance_list.append(instance_id)

            if slack_id:
                slack_client.app.client.chat_postMessage(
                    channel=slack_id,
                    text=f"사용시간이 만료되어 {instance_id} 인스턴스가 자동 종료됩니다. "
                )

    with open('instance_police.log', 'a', encoding='utf-8') as f:
        f.write(f'### {datetime.now()}\n')

        if stopped_instance_list:
            for instance_id in stopped_instance_list:
                f.write(f'{instance_id}\n')
        else:
            f.write('No instance was stopped.\n')

        f.write('\n')
