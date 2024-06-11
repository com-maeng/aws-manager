'''인스턴스 사용 할당량 초과 여부를 단속하는 모듈입니다.'''

import os
import sys
from datetime import datetime


current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(app_dir)


if __name__ == "__main__":
    from client.instance_usage_manager import InstanceUsageManager

    instance_usage_manager = InstanceUsageManager()
    stopped_instance_list = instance_usage_manager.stop_quota_exceeded_instance()

    with open('instance_police.log', 'a', encoding='utf-8') as f:
        f.write(f'### {datetime.now()}\n')

        if stopped_instance_list:
            for instance_id in stopped_instance_list:
                f.write(f'{instance_id}\n')
        else:
            f.write('No instance was stopped.\n')

        f.write('\n')
