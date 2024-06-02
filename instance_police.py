'''인스턴스 사용량 모니터 및 할당량 초과 이용시 인스턴스 종료 기능 구현.'''


import os
from datetime import timedelta, datetime

from pytz import timezone
import psycopg
import boto3
from slack_bolt import App

from app import get_remaining_instance_limit


def get_instance_running_id_list(ec2: boto3.client) -> list:
    '''running 상태의 instance id들을 반환.'''

    running_instance_id = []
    reservations = ec2.describe_instances(
        Filters=[
            {
                "Name": "instance-state-name",
                "Values": ["running"]
            }
        ]
    )['Reservations']

    for reservation in reservations:
        running_instance_id.append(reservation['Instances'][0]['InstanceId'])

    return running_instance_id


def get_today_instance_request_log(instance_id: str) -> list:
    '''사용자의 오늘 인스턴스 요청 정보를 모두 반환.'''

    with psycopg.connect(  # pylint: disable=not-context-manager
        host=os.getenv('AWS_MANAGER_DB'),
        dbname=os.getenv('AWS_MANAGER_DB_NAME'),
        user=os.getenv('AWS_MANAGER_DB_USER'),
        password=os.getenv('AWS_MANAGER_DB_USER_PW'),
    ) as conn:
        with conn.cursor() as cur:
            query = """
                    SELECT 
                        student_id
                        , instance_id
                        , request_type
                        , s.slack_id
                        , request_time
                    FROM 
                        slack_instance_request_log AS log
                    JOIN 
                        student AS s
                    ON 
                        log.student_id = s.id
                    WHERE 
                        request_time::DATE = CURRENT_DATE 
                        AND log.instance_id = %s
                    ORDER BY 
                        request_time
                    ;
                    """
            cur.execute(query, (instance_id,))
            use_logs = cur.fetchall()

    return use_logs


def check_instance(app: App,  ec2: boto3.client, instance_id_list: list):
    '''실행 되고 있는 인스턴스의 사용량을 체크하고 할당량을 모두 쓰면 종료해주는 코드.'''

    for instance_id in instance_id_list:
        use_logs = get_today_instance_request_log(instance_id)

        if use_logs == []:
            log = {
                "timestamp": datetime.now(timezone('Asia/Seoul')),
                "instance_id": instance_id,
                "event": "No log data available"
            }
            print(log)
            continue

        slack_id = use_logs[0][-2]
        remain_time = get_remaining_instance_limit(use_logs)

        if remain_time <= timedelta():  # (일일 할당 시간 - 사용시간)이 0시간 이하인지 확인
            ec2.stop_instances(InstanceIds=[instance_id], DryRun=False)

            log_data = {
                "timestamp": datetime.now(timezone('Asia/Seoul')),
                "event": "instance_stop",
                "stop_by": "system",
                "instance_id": instance_id,
                "user_slack_id": slack_id,

            }
            print(log_data)

            app.client.chat_postMessage(
                channel=slack_id,
                text=f"사용시간이 만료되어 {instance_id} 인스턴스가 자동 종료됩니다. "
            )


if __name__ == "__main__":
    ec2 = boto3.client(
        'ec2',
        aws_access_key_id=os.getenv('AWS_MANAGER_AWS_ACCESS_KEY'),
        aws_secret_access_key=os.getenv(
            'AWS_MANAGER_AWS_SECRET_ACCESS_KEY'),
        region_name='ap-northeast-2'
    )

    app = App(
        token=os.getenv('AWS_MANAGER_SLACK_BOT_TOKEN'),
        signing_secret=os.getenv('AWS_MANAGER_SLACK_SIGNING_SECRET'),
    )

    running_instance_list = get_instance_running_id_list(ec2)
    if running_instance_list:
        check_instance(app, ec2, running_instance_list)
