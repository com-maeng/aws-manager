'''정규교육일 18시에 실행 중인 모든 EC2 인스턴스를 중지합니다.'''

import os
import logging
import sys
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.FileHandler('instance_stopper.log', mode='a')],
)

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

sys.path.append(app_dir)


if __name__ == '__main__':
    from client.aws_client import EC2Client

    logging.info('인스턴스 중지 작업 시작 | %s',
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    ec2_client = EC2Client()
    running_instances = ec2_client.get_live_instance_id_list(['running'])

    if not ec2_client.stop_instance(running_instances):
        logging.error('인스턴스 중지 작업 실패 | %s',
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        sys.exit(1)

    logging.info(
        '인스턴스 중지 작업 완료 | %s | %s',
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        running_instances)
