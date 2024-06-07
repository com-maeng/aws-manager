'''인스턴스 사용량 초기화 및 할당량 초과 인스턴스 중지 기능 구현. '''

import os
from datetime import datetime, timedelta
from pytz import timezone
import psycopg
from slack_bolt import App
import boto3

from manage_usage_time import InstanceUsageManager


class InstancePolice():
    '''인스턴스 사용량 초기화 및 할당량 초과 인스턴스 중지 기능 구현.'''

    def __init__(self) -> None:
        self.ec2 = boto3.client(
            'ec2',
            aws_access_key_id=os.getenv('AWS_MANAGER_AWS_ACCESS_KEY'),
            aws_secret_access_key=os.getenv(
                'AWS_MANAGER_AWS_SECRET_ACCESS_KEY'),
            region_name='ap-northeast-2'
        )
        self.timer = InstanceUsageManager()
        self.app = App(
            token=os.getenv('AWS_MANAGER_SLACK_BOT_TOKEN'),
            signing_secret=os.getenv('AWS_MANAGER_SLACK_SIGNING_SECRET'),
        )

    def get_instance_running_list(self) -> list:
        '''running 상태의 instance id들을 반환.'''

        running_instance = []
        reservations = self.ec2.describe_instances(
            Filters=[
                {
                    "Name": "instance-state-name",
                    "Values": ["running"]
                }
            ]
        )['Reservations']

        for reservation in reservations:
            running_instance.append(reservation['Instances'][0]['InstanceId'])

        return running_instance

    def insert_log_at_midnight(self):
        '''자정마다 사용중인 인스턴스들을 system log에 적재 기능 구현.'''

        running_instance = self.get_instance_running_list()
        # print(running_instance)

        for instance_id in running_instance:
            self.timer.insert_system_logs(instance_id, 'start')

    def identify_instance_users(self, instance_id):
        '''특정 인스턴스를 사용하는 교육생을 식별.'''

        with psycopg.connect(  # pylint: disable=not-context-manager
            host=os.getenv('AWS_MANAGER_DB'),
            dbname=os.getenv('AWS_MANAGER_DB_NAME'),
            user=os.getenv('AWS_MANAGER_DB_USER'),
            password=os.getenv('AWS_MANAGER_DB_USER_PW'),
        ) as conn:
            with conn.cursor() as cur:
                query = '''
                        SELECT 
                            DISTINCT slack_id
                        FROM 
                            student AS s 
                        JOIN (
                            SELECT 
                                DISTINCT student_id
                            FROM 
                                slack_instance_request_log
                            WHERE 
                                instance_id = %s
                            ) AS r_log
                        ON 
                            s.id = r_log.student_id
                        ;
                        '''
                cur.execute(query, (instance_id,))
                slack_id = cur.fetchall()
        if slack_id != []:
            slack_id = slack_id[-1][0]

        return slack_id

    def auto_stop_exceeded_instance(self):
        '''할당 사용 시간을 넘긴 인스턴스들 자동 종료 기능 구현.'''

        running_instance = self.get_instance_running_list()

        for instance_id in running_instance:
            remain_time = self.timer.get_remaining_time(instance_id)

            if remain_time <= timedelta():
                slack_id = self.identify_instance_users(instance_id)

                self.ec2.stop_instances(
                    InstanceIds=[instance_id], DryRun=False)

                self.timer.insert_system_logs(instance_id, 'stop')

                if slack_id != []:
                    self.app.client.chat_postMessage(
                        channel=slack_id,
                        text=f"사용시간이 만료되어 {instance_id} 인스턴스가 자동 종료됩니다. "
                    )


if __name__ == "__main__":
    instance_police = InstancePolice()
    midnight_time = datetime.combine(
        datetime.now(timezone('Asia/Seoul')),
        datetime.min.time()
    )

    if datetime.now() == midnight_time:
        instance_police.insert_log_at_midnight()

    instance_police.auto_stop_exceeded_instance()
