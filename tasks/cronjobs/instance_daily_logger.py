'''매일 자정마다 running 상태의 인스턴스를 system log에 적재합니다.'''


import os
import sys


current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)

if __name__ == "__main__":
    from client.instance_usage_manager import InstanceUsageManager

    instance_usage_manager = InstanceUsageManager()
    running_instance_list = instance_usage_manager.get_running_instance_list()

    for instance_id in running_instance_list:
        instance_usage_manager.timer.insert_system_logs(instance_id, 'start')
