'''An entry point of the Flask application.

Example:
    $ gunicorn --workers 2 --bind 127.0.0.1:4202 app:app
'''


import logging
from datetime import datetime, timedelta

from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request

from pytz import timezone

from client.slack_client import SlackClient
from client.aws_client import EC2Client
from client.psql_client import PSQLClient
from client.instance_usage_manager import InstanceUsageManager


# Set up a root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.FileHandler('app.log', mode='a')]
)

ec2_client = EC2Client()
slack_client = SlackClient()
psql_client = PSQLClient()
instance_usage_manager = InstanceUsageManager()

app = Flask(__name__)
slack_app = slack_client.app
slack_req_handler = SlackRequestHandler(slack_app)


@slack_app.command('/stop')
def handle_stop_command(ack, say, command) -> bool:
    '''인스턴스 중지 커맨드(/stop)를 처리합니다.'''

    ack()  # 3초 이내 응답 필요

    # 사용자 입력값의 가장 마지막에 인스턴스 ID가 위치한다고 가정
    instance_id = command['text'].split()[-1]

    slack_id = command['user_id']
    instance_state = ec2_client.get_instance_state(instance_id)

    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)
    except ValueError:
        say('이어드림스쿨 4기 교육생이 아니면 인스턴스를 중지할 수 없습니다.')
        logging.info('교육생이 아닌 사용자의 `/stop` 요청 | slack_id: %s', slack_id)

        return False

    if track != 'DE':
        say('현재는 DE 트랙 교육생이 아니면 인스턴스를 중지할 수 없습니다.')
        logging.info('DE 트랙 외 교육생의 `/stop` 요청 | slack_id: %s', slack_id)

        return False

    if instance_state != 'running':
        say('인스턴스가 시작(running) 상태일 때만 중지할 수 있습니다.')
        logging.info(
            '시작 상태가 아닌 인스턴스 `/stop` 요청 | 인스턴스 상태: %s',
            instance_state
        )

        return False

    instance_onwer = psql_client.get_slack_id_by_instance(instance_id)

    if slack_id != instance_onwer:
        say('자신의 소유의 인스턴스만 종료할 수 있습니다.')
        logging.info(
            '자신의 소유가 아닌 인스턴스 `/stop` 요청 | slack_id: %s', slack_id
        )
        return False

    ec2_client.stop_instance(instance_id)

    today_logs = psql_client.get_today_instance_logs(instance_id)
    remaining_time = instance_usage_manager.get_remaining_time(today_logs)

    remain_hours, remain_minutes, _ = str(remaining_time).split(':')
    now = datetime.now(timezone('Asia/Seoul'))
    msg = f'''
{instance_id}를 종료했습니다.

- 오늘의 잔여 할당량: {remain_hours}시간 {remain_minutes}분 
- 인스턴스 종료 시간: {now.strftime('%Y-%m-%d %H:%M분')}

*인스턴스 사용량 초기화는 매일 자정에 진행됩니다.*
    '''

    say(msg)
    psql_client.insert_instance_request_log(
        student_id,
        instance_id,
        'stop',
        str(now)
    )

    return True


@slack_app.command('/start')
def handle_start_command(ack, say, command) -> bool:
    '''인스턴스 시작 커맨드(/start)를 처리합니다.'''

    ack()  # 3초 이내 응답 필요

    # 사용자 입력값의 가장 마지막에 인스턴스 ID가 위치한다고 가정
    instance_id = command['text'].split()[-1]

    slack_id = command['user_id']
    instance_state = ec2_client.get_instance_state(instance_id)

    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)
    except ValueError:
        say('이어드림스쿨 4기 교육생이 아니면 인스턴스를 시작할 수 없습니다.')
        logging.info('교육생이 아닌 사용자의 `/start` 요청 | slack_id: %s', slack_id)

        return False

    if track != 'DE':
        say('현재는 DE 트랙 교육생이 아니면 인스턴스를 시작할 수 없습니다.')
        logging.info('DE 트랙 외 교육생 `/start` 요청 | slack_id: %s', slack_id)

        return False

    instance_onwer = psql_client.get_slack_id_by_instance(instance_id)
    if slack_id != instance_onwer:
        say('자신의 소유의 인스턴스만 시작할 수 있습니다.')
        logging.info(
            '자신의 소유가 아닌 인스턴스 `/start` 요청 | slack_id: %s', slack_id
        )
        return False

    if instance_state != 'stopped':
        say('인스턴스가 중지(stopped) 상태일 때만 시작할 수 있습니다.')
        logging.info(
            '중지 상태가 아닌 인스턴스 `/start` 요청 | 인스턴스 상태: %s',
            instance_state
        )

        return False

    today_logs = psql_client.get_today_instance_logs(instance_id)
    remaining_time = instance_usage_manager.get_remaining_time(today_logs)

    if remaining_time <= timedelta():  # (일일 할당량 - 사용시간) <= 0
        say('인스턴스 사용 할당량을 초과했습니다.')
        logging.info(
            '인스턴스 사용 할당량 초과 상태에서 `/start` 요청 | slack_id: %s',
            slack_id
        )

        return False

    ec2_client.start_instance(instance_id)

    remain_hours, remain_minutes, _ = str(remaining_time).split(":")
    now = datetime.now(timezone('Asia/Seoul'))
    msg = f'''
{instance_id}를 시작했습니다.

- 오늘의 잔여 할당량: {remain_hours}시간 {remain_minutes}분 
- 인스턴스 시작 시간: {now.strftime('%Y-%m-%d %H:%M분')}
- 인스턴스 최대 사용 시간: {(now + remaining_time).strftime('%Y-%m-%d %H:%M분')}

*인스턴스 사용량 초기화는 매일 자정에 진행됩니다.*
    '''

    say(msg)
    psql_client.insert_instance_request_log(
        student_id,
        instance_id,
        'start',
        str(now)
    )

    return True


@app.route('/slack/events', methods=['POST'])
def handle_slack_events():
    '''슬랙에서 송신된 이벤트 관련 request를 처리합니다.'''

    return slack_req_handler.handle(request)
