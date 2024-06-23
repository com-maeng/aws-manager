'''An entry point of the Flask application.

Example:
    $ gunicorn --workers 2 --bind 127.0.0.1:4202 app:app
'''


import asyncio
import logging
from datetime import datetime, timedelta, time

from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request

from pytz import timezone


from client.slack_client import SlackClient
from client.aws_client import EC2Client, IAMClient
from client.psql_client import PSQLClient
from client.instance_usage_manager import InstanceUsageManager


# Set up a root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[logging.FileHandler('app.log', mode='a')]
)

ec2_client = EC2Client()
iam_client = IAMClient()
slack_client = SlackClient()
psql_client = PSQLClient()
instance_usage_manager = InstanceUsageManager()

app = Flask(__name__)
slack_app = slack_client.app

slack_req_handler = SlackRequestHandler(slack_app)


@slack_app.command('/show')
def handle_show_command(ack, say, command) -> bool:
    '''사용자 소유의 인스턴스 상태 조회 커맨드(/show)를 처리합니다.'''

    ack()  # 3초 이내 응답 필요

    slack_id = command['user_id']
    owned_instance_id_list = psql_client.get_user_owned_instance(slack_id)
    instance_state_list = []
    instance_state_pairs = []

    if not owned_instance_id_list:
        say('현재 소유 중인 인스턴스가 없습니다.')
        logging.info('소유 중인 인스턴스가 없는 사용자의 `/show` 요청 | slack_id: %s', slack_id)

        return False

    for owned_instance_id in owned_instance_id_list:
        instance_state = ec2_client.get_instance_state(owned_instance_id)

        instance_state_list.append(instance_state)

    for tup in zip(owned_instance_id_list, instance_state_list):
        # - i-1234567890abcdef0 : running, - i-abcdef1234567890 : stopped, ...
        instance_state_pairs.append(f'- {tup[0]} : {tup[1]}')

    msg = '\n'.join(instance_state_pairs)

    say(msg)
    logging.info('인스턴스 상태 조회 요청 | slack_id: %s', slack_id)

    return True


@slack_app.command('/stop')
def handle_stop_command(ack, say, command) -> bool:
    '''인스턴스 중지 커맨드(/stop)를 처리합니다.'''

    ack()  # 3초 이내 응답 필요

    slack_id = command['user_id']

    # 교육생 여부 및 트랙 체크
    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)

        assert track == 'DE'
    except ValueError as e:
        say('이어드림스쿨 4기 교육생이 아니면 인스턴스를 중지할 수 없습니다.')
        logging.info(
            '교육생이 아닌 슬랙 유저의 `/stop` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False
    except AssertionError as e:
        say('현재는 DE 트랙 교육생이 아니면 인스턴스를 중지할 수 없습니다.')
        logging.info(
            'DE 트랙 외 교육생의 `/stop` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False

    # 소유 중인 인스턴스 조회
    instance_id_list = psql_client.get_user_owned_instance(student_id)

    if not instance_id_list:
        say('현재 소유 중인 인스턴스가 없습니다.')
        logging.info(
            '소유 중인 인스턴스가 없는 사용자의 `/stop` 요청 | 슬랙 ID: %s',
            slack_id
        )

        return False

    # `stopped` 상태로 만들 인스턴스가 하나라도 있는지 확인
    instance_state_dict = ec2_client.get_instance_state(instance_id_list)
    state_values = instance_state_dict.values()

    if not any(value == 'running' for value in state_values):
        say('이미 모든 인스턴스가 `stopped` 상태입니다.')
        logging.info(
            '`stopped`로 상태를 변경할 수 있는 인스턴스가 없는 상황에서의 `/stop` 요청 | 인스턴스 상태: %s',
            instance_state_dict
        )

        return False

    # 인스턴스 중지
    if not ec2_client.stop_instance(instance_id_list):
        say('알 수 없는 이유로 인스턴스 중지에 실패했습니다.')
        logging.error('인스턴스 중지 실패 | 인스턴스 ID: %s', instance_id_list)

        return False

    logging.info('인스턴스 중지 | 인스턴스 ID: %s', instance_id_list)

    # 성공 메시지 전송
    remaining_tm = psql_client.get_remaining_usage_time(student_id)
    now = datetime.now(timezone('Asia/Seoul'))
    msg = f'''\
모든 인스턴스를 성공적으로 중지했습니다 🚀
오늘의 잔여 할당량: `{remaining_tm.hour}시간 {remaining_tm.minute}분 {remaining_tm.second}초`

_인스턴스 할당량 초기화는 매일 자정에 진행됩니다._\
    '''

    say(msg)

    # 로그 데이터 적재
    psql_client.insert_instance_request_log(
        student_id,
        'stop',
        str(now.strftime('%Y-%m-%d %H:%M:%S'))
    )

    return True


@slack_app.command('/start')
def handle_start_command(ack, say, command) -> bool:
    '''인스턴스 시작 커맨드(/start)를 처리합니다.'''

    ack()  # 3초 이내 응답 필요

    slack_id = command['user_id']

    # 교육생 여부 체크
    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)
    except ValueError as e:
        say('이어드림스쿨 4기 교육생이 아니면 인스턴스를 시작할 수 없습니다.')
        logging.info(
            '교육생이 아닌 슬랙 유저의 `/start` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False

    # DE 트랙 교육생 여부 체크
    if track != 'DE':
        say('현재는 DE 트랙 교육생이 아니면 인스턴스를 시작할 수 없습니다.')
        logging.info('DE 트랙 외 교육생의 `/start` 요청 | 슬랙 ID: %s', slack_id)

        return False

    # 소유 중인 인스턴스 조회
    instance_id_list = psql_client.get_user_owned_instance(student_id)

    if not instance_id_list:
        say('현재 소유 중인 인스턴스가 없습니다.')
        logging.info(
            '소유 중인 인스턴스가 없는 사용자의 `/start` 요청 | 슬랙 ID: %s',
            slack_id
        )

        return False

    # `running` 상태로 만들 인스턴스가 하나라도 있는지 확인
    instance_state_dict = ec2_client.get_instance_state(instance_id_list)
    state_values = instance_state_dict.values()

    if not any(value == 'stopped' for value in state_values):
        say('이미 모든 인스턴스가 `running` 상태입니다.')
        logging.info(
            '`running`으로 상태를 변경할 수 있는 인스턴스가 없는 상황에서의 `/start` 요청 | 인스턴스 상태: %s',
            instance_state_dict
        )

        return False

    # 인스턴스 사용 할당량 초과 여부 확인
    remaining_tm = psql_client.get_remaining_usage_time(student_id)

    if remaining_tm == time.min:
        msg = '''\
오늘의 인스턴스 사용 할당량을 모두 초과하였습니다.

💡 일별 할당량
- 평일 할당량: 6시간
- 주말 할당량: 12시간\
        '''

        say(msg)
        logging.info(
            '인스턴스 사용 할당량 초과 상태에서 `/start` 요청 | 슬랙 ID: %s',
            slack_id
        )

        return False

    # 인스턴스 시작
    if not ec2_client.start_instance(instance_id_list):
        say('알 수 없는 이유로 인스턴스 시작에 실패했습니다.')
        logging.error('인스턴스 시작 실패 | 인스턴스 ID: %s', instance_id_list)

        return False

    logging.info('인스턴스 시작 | 인스턴스 ID: %s', instance_id_list)

    # 성공 메시지 전송
    now = datetime.now(timezone('Asia/Seoul'))
    maximum_usage_time = now + timedelta(
        hours=remaining_tm.hour,
        minutes=remaining_tm.minute,
        seconds=remaining_tm.second
    )
    msg = f'''\
인스턴스를 성공적으로 시작했습니다 🚀
인스턴스를 사용한 다음에는 반드시 `/stop` 명령어로 종료해주세요 ⚠️

- 오늘의 잔여 할당량: `{remaining_tm.hour}시간 {remaining_tm.minute}분 {remaining_tm.second}초`
- 인스턴스 최대 사용 가능 시간: `{maximum_usage_time.strftime('%Y-%m-%d %H:%M:%S')}`

_인스턴스 할당량 초기화는 매일 자정에 진행됩니다._\
    '''

    say(msg)

    # 로그 데이터 적재
    psql_client.insert_instance_request_log(
        student_id,
        'start',
        str(now.strftime('%Y-%m-%d %H:%M:%S'))
    )

    return True


@slack_app.command('/policy')
def handle_policy_command(ack, say, command) -> bool:
    '''AWS 임시 콘솔 접근 부여 커맨드(/policy)를 처리합니다.'''

    ack()

    slack_id = command['user_id']
    now = datetime.now(timezone('Asia/Seoul'))

    # 교육생 여부 체크
    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)

    except ValueError as e:
        say('이어드림스쿨 4기 교육생이 아니면 AWS 콘솔 접근 권한을 부여받을 수 없습니다.')
        logging.info(
            '교육생이 아닌 슬랙 유저의 `/policy` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False

    # DE 트랙 교육생 여부 체크
    if track != 'DE':
        say('현재는 DE 트랙 교육생이 아니면 AWS 콘솔 접근 권한을 부여받을 수 없습니다.')
        logging.info('DE 트랙 외 교육생의 `/policy` 요청 | 슬랙 ID: %s', slack_id)

        return False

    policy_reqeust_count = psql_client.get_policy_request_count(student_id)

    if not policy_reqeust_count:
        say('데이터를 불러오는 중에 문제가 발생했습니다. 관리자에게 문의해주세요!')
        logging.info('`/policy` 요청에서의 DB 접근 오류 | 슬랙 ID: %s', slack_id)

        return False

    if policy_reqeust_count[0][0] > 4:
        msg = '''\
오늘은 더이상 임시 콘솔 접근 권한을 요청할 수 없습니다.:melting_face:
임시 콘솔 접근 권한은 매일 15분씩 총 4번까지 가능합니다. 
'''

        say(msg)

        logging.info(
            '`/policy` 요청 횟수 초과 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False

    async def access_permissions_manager(iam_user_name: str) -> None:
        STUDENT_POLICY_ARN = 'arn:aws:iam::473952381102:policy/GeneralStudentsPolicy'  # pylint: disable=invalid-name

        # 접근 권한 부여
        if not iam_client.attach_user_policy(iam_user_name, STUDENT_POLICY_ARN):
            say('AWS 콘솔 접근 권한 부여 중 문제가 발생하였습니다.:scream: 관리자에게 문의해주세요!')
            logging.info('`/policy` 요청에서의 DB 접근 오류 | 슬랙 ID: %s', slack_id)

            return False

        msg = '''\
AWS 콘솔 접근 권한을 드렸습니다. 🚀
지금부터 15분간 AWS콘솔에 접근할 수 있습니다. 
        '''

        say(msg)

        # 로그 데이터 적재
        psql_client.insert_instance_request_log(
            student_id,
            'policy',
            str(now.strftime('%Y-%m-%d %H:%M:%S'))
        )

        await asyncio.sleep(900)

        # 접근 권한 회수
        if not iam_client.detach_user_policy(iam_user_name, STUDENT_POLICY_ARN):
            say('AWS 콘솔 접근 권한 회수 중 문제가 발생하였습니다.:scream: 관리자에게 문의해주세요!')

            return False

        msg = f'''\
15분이 경과하여 콘솔 접근 권한이 회수되었습니다. :smiling_face_with_tear:
⚠️ 오늘 콘솔 접근 권한 요청은 {4 - policy_reqeust_count}번 남았습니다.
'''

        say(msg)

        return True

    iam_user_name = psql_client.get_iam_user_name(student_id)

    if iam_user_name:
        # 비동기 함수 호출 및 실행
        asyncio.run(access_permissions_manager(iam_user_name))

    return True


@app.route('/slack/events', methods=['POST'])
def handle_slack_events():
    '''슬랙에서 송신된 이벤트 관련 request를 처리합니다.'''

    return slack_req_handler.handle(request)
