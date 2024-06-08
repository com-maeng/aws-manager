'''An entry point for the Slack application.

Example:
    $ gunicorn -w 2 --bind 127.0.0.1:4202 app:flask_app
'''


import os
from datetime import datetime, timedelta

from pytz import timezone
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
import boto3
import botocore.exceptions
from flask import Flask, request
import psycopg

from manage_usage_time import InstanceUsageManager

app = App(
    token=os.getenv('AWS_MANAGER_SLACK_BOT_TOKEN'),
    signing_secret=os.getenv('AWS_MANAGER_SLACK_SIGNING_SECRET'),
)
ec2 = boto3.client(
    'ec2',
    aws_access_key_id=os.getenv('AWS_MANAGER_AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv(
        'AWS_MANAGER_AWS_SECRET_ACCESS_KEY'),
    region_name='ap-northeast-2'
)
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)


def get_user_info(user_id: str) -> tuple:
    '''사용자의 정보를 반환.'''

    with psycopg.connect(  # pylint: disable=not-context-manager
        host=os.getenv('AWS_MANAGER_DB'),
        dbname=os.getenv('AWS_MANAGER_DB_NAME'),
        user=os.getenv('AWS_MANAGER_DB_USER'),
        password=os.getenv('AWS_MANAGER_DB_USER_PW'),
    ) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    track
                    , id
                FROM 
                    student
                WHERE 
                    slack_id = %s
                ;
                """
            cur.execute(query, (user_id,))
            user_info = cur.fetchone()

    return (None, None) if user_info is None else user_info


def get_instance_state(ec2: boto3.client, instance_id: str) -> str:
    '''인스턴스의 상태 정보를 반환.'''

    try:
        reservations = ec2.describe_instances(
            InstanceIds=[instance_id]
        )['Reservations']
        instance_status = reservations[0]['Instances'][0]['State']['Name']
        return instance_status
    except botocore.exceptions.ClientError:
        return 'error'


def insert_instance_request_log(student_id: str, instance_id: str, request_type: str) -> None:
    '''인스턴스 요청 로그 저장.'''

    with psycopg.connect(  # pylint: disable=not-context-manager
        host=os.getenv('AWS_MANAGER_DB'),
        dbname=os.getenv('AWS_MANAGER_DB_NAME'),
        user=os.getenv('AWS_MANAGER_DB_USER'),
        password=os.getenv('AWS_MANAGER_DB_USER_PW'),
    ) as conn:
        with conn.cursor() as cur:
            insert_query = """
                            INSERT INTO
                                slack_instance_request_log (
                                    student_id
                                    , instance_id
                                    , request_type
                                    , request_time
                                )
                            VALUES
                                (%s, %s, %s, %s)
                            ;
                            """
            cur.execute(insert_query,
                        (student_id, instance_id, request_type, str(
                            datetime.now(timezone('Asia/Seoul'))))
                        )

            conn.commit()


@app.command('/start')
def handle_start_command(ack, say, command):
    '''인스턴스 시작 커맨드(/start) 처리.

    Args:
        ack: `ack()` utility function, which returns acknowledgement to the Slack servers.
        command: An alias for payload in an `@app.command` listener.
    '''

    ack()

    user_id = command['user_id']
    request_instance_id = command['text'].strip()

    manager = InstanceUsageManager()

    track, student_id = get_user_info(user_id)
    if track is None:
        say("EC2를 사용 할 수 없는 사용자 입니다. 사용하고 싶으시면 문의 해주세요.")
        return False
    elif track != 'DE':
        say("DS track은 아직 인스턴스를 사용할 수 없습니다")
        return False

    instance_state = get_instance_state(ec2, request_instance_id)
    if instance_state == 'error':
        say("존재하지 않는 인스턴스 id 입니다. 인스턴스 id를 다시 확인해주세요")
        return False
    elif instance_state != "stopped":
        say(f"인스턴스가 {instance_state} 상태입니다. 인스턴스는 중지 상태일때만 시작할 수 있습니다.")
        return False

    limit_time = manager.get_remaining_time(request_instance_id)

    if limit_time <= timedelta():  # (일일 할당 시간 - 사용시간)이 0시간 이하인지 확인
        say("아쉽지만 오늘의 사용시간을 초과하였습니다.")
        return False

    ec2.start_instances(InstanceIds=[request_instance_id], DryRun=False)

    limit_hours, limit_minutes, _ = str(limit_time).split(":")
    now = datetime.now()

    say(
        f"""
{request_instance_id}를 시작합니다.
오늘의 잔여량:  {limit_hours}시간 {limit_minutes}분 
인스턴스 시작 시간: {now.strftime('%Y-%m-%d %H시 %M분')}
인스턴스 최대 사용 시간: {(now + limit_time).strftime('%Y-%m-%d %H시 %M분')}
[인스턴스 사용 시간은 매일 자정에 재할당되는 점 참고해서 사용해주세요.]
        """
    )

    insert_instance_request_log(student_id, request_instance_id, "start")


@flask_app.route('/slack/events', methods=['POST'])
def handle_slack_events():
    '''Hanle Slack events within Flask.
    '''

    return handler.handle(request)
