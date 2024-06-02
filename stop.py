'''An entry point for the Slack application.

Example:
    $ gunicorn -w 2 --bind 127.0.0.1:4202 app:flask_app
'''


import os
from datetime import datetime, timedelta

from pytz import timezone
import holidays
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
import boto3
import botocore.exceptions
from flask import Flask, request
import psycopg


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
            query = '''
                SELECT 
                    track
                    , id
                FROM 
                    student
                WHERE 
                    slack_id = %s
                ;
                '''
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


def get_today_instance_request_log(user_id: str) -> list:
    '''사용자의 오늘 인스턴스 요청 정보를 모두 반환.'''

    with psycopg.connect(  # pylint: disable=not-context-manager
        host=os.getenv('AWS_MANAGER_DB'),
        dbname=os.getenv('AWS_MANAGER_DB_NAME'),
        user=os.getenv('AWS_MANAGER_DB_USER'),
        password=os.getenv('AWS_MANAGER_DB_USER_PW'),
    ) as conn:
        with conn.cursor() as cur:
            query = '''
                    SELECT 
                        student_id
                        , instance_id
                        , request_type
                        , request_time
                    FROM 
                        slack_instance_request_log AS log
                    JOIN (
                        SELECT 
                            id
                        FROM 
                            student
                        WHERE 
                            slack_id = %s
                    )  AS s
                    ON 
                        log.student_id = s.id
                    WHERE 
                        request_time::DATE = CURRENT_DATE
                    ORDER BY 
                        request_time
                    ;
                    '''
            cur.execute(query, (user_id,))
            use_logs = cur.fetchall()

    return use_logs


def get_throshold_time() -> datetime:
    '''인스턴스 일별 할당량 시간 계산 함수.'''

    year = datetime.now().year
    kr_holidays = holidays.country_holidays('KR', years=year)
    today = datetime.now(timezone('Asia/Seoul')).date()

    if today in kr_holidays or today.weekday() >= 5:
        threshold_time = 12
    else:
        threshold_time = 6

    return threshold_time


def get_remaining_instance_limit(use_logs: list) -> datetime:
    '''사용자의 잔여 인스턴스 사용 가능 시간을 반환.'''

    today = datetime.now(timezone('Asia/Seoul'))
    delta_time = timedelta()
    midnight_time = datetime.combine(
        today.date(), datetime.min.time())

    for i, log in enumerate(use_logs):
        request_type_log = log[2]
        request_time_log = log[-1]

        if i == 0 and request_type_log == 'stop':  # 새벽 종료시 사용 시간 계산
            delta_time += (request_time_log - midnight_time)

        # 시스템 로직이 인스턴스 종료 시, 사용 시간 계산
        elif i == len(use_logs) - 1 and request_type_log == 'start':
            delta_time += (today -
                           request_time_log.astimezone(timezone('Asia/Seoul')))

        elif request_type_log == 'start':  # start ~ stop의 시간 계산
            next_log = use_logs[i+1]
            next_request_time = next_log[-1]
            next_request_type = next_log[2]
            if next_request_type == 'stop':
                delta_time += (next_request_time - request_time_log)

    threshold_time = get_throshold_time()
    limit_time = timedelta(hours=threshold_time) - delta_time

    return limit_time


def insert_instance_request_log(student_id: str, instance_id: str, request_type: str) -> None:
    '''인스턴스 요청 로그 저장.'''

    with psycopg.connect(  # pylint: disable=not-context-manager
        host=os.getenv('AWS_MANAGER_DB'),
        dbname=os.getenv('AWS_MANAGER_DB_NAME'),
        user=os.getenv('AWS_MANAGER_DB_USER'),
        password=os.getenv('AWS_MANAGER_DB_USER_PW'),
    ) as conn:
        with conn.cursor() as cur:
            insert_query = '''
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
                            '''
            cur.execute(insert_query,
                        (student_id, instance_id, request_type, str(
                            datetime.now(timezone('Asia/Seoul'))))
                        )

            conn.commit()


def check_right_user_instance(student_id):
    '''사용자가 바로 이전에 요청했던 instance id와 동일한지 확인.'''

    with psycopg.connect(  # pylint: disable=not-context-manager
        host=os.getenv('AWS_MANAGER_DB'),
        dbname=os.getenv('AWS_MANAGER_DB_NAME'),
        user=os.getenv('AWS_MANAGER_DB_USER'),
        password=os.getenv('AWS_MANAGER_DB_USER_PW'),
    ) as conn:
        with conn.cursor() as cur:
            query = '''
                SELECT 
                    instance_id
                FROM 
                    slack_instance_request_log AS log
                WHERE 
                    request_type = 'start'
                    AND student_id = %s
                ORDER BY
                    request_time DESC 
                LIMIT  1
                ;
                '''
            cur.execute(query, (student_id,))
            pre_use_instance_id = cur.fetchone()
    return pre_use_instance_id


@app.command('/stop')
def handle_stop_command(ack, say, command):
    '''인스턴스 중지 커맨드(/stop) 처리.'''

    ack()

    user_id = command['user_id']
    request_instance_id = command['text'].split()[-1]

    track, student_id = get_user_info(user_id)
    if track is None:
        say('EC2를 사용 할 수 없는 사용자 입니다. 사용하고 싶으시면 문의 해주세요.')
        return False
    elif track != 'DE':
        say('DS track은 아직 인스턴스를 사용할 수 없습니다.')
        return False

    instance_state = get_instance_state(ec2, request_instance_id)
    if instance_state == 'error':
        say('존재하지 않는 인스턴스 id 입니다. 인스턴스 id를 다시 확인해주세요.')
        return False
    elif instance_state != 'running':
        say(f'인스턴스가 {instance_state} 상태입니다. 인스턴스는 running 상태일때만 종료할 수 있습니다.')
        return False

    before_use_instance_id = check_right_user_instance(student_id)[0]
    if before_use_instance_id != request_instance_id:
        say('이전에 시작을 요청한 instance id와 동일한 id가 아닙니다. 확인해주세요.')
        return False

    ec2.stop_instances(InstanceIds=[request_instance_id], DryRun=False)
    insert_instance_request_log(student_id, request_instance_id, 'stop')

    instance_use_log = get_today_instance_request_log(user_id)
    limit_time = get_remaining_instance_limit(instance_use_log)
    limit_hours, limit_minutes, _ = str(limit_time).split(':')
    now = datetime.now()

    say(
        f'''
{request_instance_id}를 종료합니다.
인스턴스 종료 시간 : {now.strftime('%Y-%m-%d %H시 %M분')}
오늘의 남은 잔여 시간 : {limit_hours}시간 {limit_minutes}분
        '''
    )


@flask_app.route('/slack/events', methods=['POST'])
def handle_slack_events():
    '''Hanle Slack events within Flask.
    '''

    return handler.handle(request)
