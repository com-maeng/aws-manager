'''An entry point of the Flask application.

Example:
    $ gunicorn --workers 2 --bind 127.0.0.1:4202 app:app
'''


import os
import threading
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
def handle_show_command(ack, command) -> bool:
    '''사용자 소유의 인스턴스 상태 조회 커맨드(/show)를 처리합니다.'''

    slack_id = command['user_id']
    msg = '인스턴스 상태를 조회하는 중입니다... 🔎'

    ack()  # 3초 이내 응답 필요
    slack_client.send_dm(slack_id, msg)

    # 교육생 여부 및 트랙 체크
    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)

        assert track == 'DE'
    except TypeError as e:
        msg = '이어드림스쿨 4기 교육생이 아니면 인스턴스의 상태를 조회할 수 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            '교육생이 아닌 슬랙 유저의 `/show` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False
    except AssertionError as e:
        msg = '현재는 DE 트랙 교육생이 아니면 인스턴스의 상태를 조회할 수 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            'DE 트랙 외 교육생의 `/show` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

    user_owned_instance_list = psql_client.get_user_owned_instance(student_id)

    # 소유 중인 인스턴스 조회
    if not user_owned_instance_list:
        msg = '현재 소유 중인 인스턴스가 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info('소유 중인 인스턴스가 없는 사용자의 `/show` 요청 | slack_id: %s', slack_id)

        return False

    # 인스턴스 상태 조회
    instance_info_dict = ec2_client.get_instance_info(
        user_owned_instance_list)

    if not instance_info_dict:
        msg = '알 수 없는 이유로 인스턴스 상태 조회에 실패했습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.error('인스턴스 상태 조회 실패 | 인스턴스 ID: %s', user_owned_instance_list)

        return False

    # 상태 정보 메시지 전송, 로그 데이터 적재
    now = datetime.now(timezone('Asia/Seoul'))
    msg = '조회된 인스턴스 목록 📝\n\n'
    instance_info_str_list = []

    for k, v in instance_info_dict.items():
        instance_info_str_list.append(
            f'- `{v["name"]}` : {k} | {v["instance_state"]} | \
Public IP Address - {v["public_ip_address"]} | Private IP Address - {v["private_ip_address"]}')
    msg += '\n'.join(instance_info_str_list)

    slack_client.send_dm(slack_id, msg)
    logging.info('인스턴스 상태 조회 요청 | slack_id: %s', slack_id)
    psql_client.insert_slack_user_request_log(
        student_id,
        'show',
        str(now.strftime('%Y-%m-%d %H:%M:%S'))
    )

    return True


@slack_app.command('/stop')
def handle_stop_command(ack, command) -> bool:
    '''인스턴스 중지 커맨드를(`/stop`) 처리합니다.'''

    slack_id = command['user_id']
    msg = '인스턴스를 중지하는 중입니다... 😴'

    ack()  # 3초 이내 응답 필요
    slack_client.send_dm(slack_id, msg)

    # 교육생 여부 및 트랙 체크
    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)
        assert track == 'DE'
    except TypeError as e:
        msg = '이어드림스쿨 4기 교육생이 아니면 인스턴스를 중지할 수 없습니다.'
        slack_client.send_dm(slack_id, msg)

        logging.info(
            '교육생이 아닌 슬랙 유저의 `/stop` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )
        return False
    except AssertionError as e:
        msg = '현재는 DE 트랙 교육생이 아니면 인스턴스를 중지할 수 없습니다.'
        slack_client.send_dm(slack_id, msg)

        logging.info(
            'DE 트랙 외 교육생의 `/stop` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )
        return False

    # 소유 중인 인스턴스 조회
    user_owned_instance_list = psql_client.get_user_owned_instance(student_id)
    if not user_owned_instance_list:
        msg = '현재 소유 중인 인스턴스가 없습니다.'
        slack_client.send_dm(slack_id, msg)

        logging.info(
            '소유 중인 인스턴스가 없는 사용자의 `/stop` 요청 | 슬랙 ID: %s',
            slack_id
        )
        return False

    # 인스턴스 상태 조회
    instance_info_dict = ec2_client.get_instance_info(
        user_owned_instance_list)
    if not instance_info_dict:
        msg = '알 수 없는 이유로 인스턴스 상태 조회에 실패했습니다.'
        slack_client.send_dm(slack_id, msg)

        logging.error('인스턴스 상태 조회 실패 | 인스턴스 ID: %s', user_owned_instance_list)
        return False

    # `stopped` 상태로 만들 인스턴스가 하나라도 있는지 확인
    state_values = []
    for single_info_dict in instance_info_dict.values():
        state_values.append(single_info_dict['instance_state'])

    if not any(value == 'running' for value in state_values):
        msg = '이미 모든 인스턴스가 `stopped` 상태입니다.'
        slack_client.send_dm(slack_id, msg)

        logging.info(
            '`stopped`로 상태를 변경할 수 있는 인스턴스가 없는 상황에서의 `/stop` 요청 | 인스턴스 상태: %s', instance_info_dict)
        return False

    # 인스턴스 중지
    if not ec2_client.stop_instance(user_owned_instance_list):
        msg = '알 수 없는 이유로 인스턴스 중지에 실패했습니다.'
        slack_client.send_dm(slack_id, msg)

        logging.error('인스턴스 중지 실패 | 인스턴스 ID: %s', user_owned_instance_list)
        return False

    logging.info('인스턴스 중지 | 인스턴스 ID: %s', user_owned_instance_list)

    # 성공 메시지 전송, 로그 데이터 적재
    now = datetime.now(timezone('Asia/Seoul'))
    remaining_tm = psql_client.get_remaining_usage_time(student_id)
    msg = f'''\
모든 인스턴스를 성공적으로 중지했습니다 🛌
- 오늘의 잔여 할당량: `{remaining_tm.hour}시간 {remaining_tm.minute}분 {remaining_tm.second}초`

_인스턴스 할당량 초기화는 매일 자정에 진행됩니다._\
    '''

    slack_client.send_dm(slack_id, msg)
    psql_client.insert_slack_user_request_log(
        student_id,
        'stop',
        str(now.strftime('%Y-%m-%d %H:%M:%S'))
    )

    return True


@slack_app.command('/start')
def handle_start_command(ack, command) -> bool:
    '''인스턴스 시작 커맨드(/start)를 처리합니다.'''

    slack_id = command['user_id']
    msg = '인스턴스를 시작하는 중입니다... 🚀'

    ack()  # 3초 이내 응답 필요
    slack_client.send_dm(slack_id, msg)

    # 교육생 여부 및 트랙 체크
    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)

        assert track == 'DE'
    except TypeError as e:
        msg = '이어드림스쿨 4기 교육생이 아니면 인스턴스를 시작할 수 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            '교육생이 아닌 슬랙 유저의 `/start` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False
    except AssertionError as e:
        msg = '현재는 DE 트랙 교육생이 아니면 인스턴스를 시작할 수 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            'DE 트랙 외 교육생의 `/start` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False

    # 소유 중인 인스턴스 조회
    user_owned_instance_list = psql_client.get_user_owned_instance(student_id)
    if not user_owned_instance_list:
        msg = '현재 소유 중인 인스턴스가 없습니다.'
        slack_client.send_dm(slack_id, msg)

        logging.info(
            '소유 중인 인스턴스가 없는 사용자의 `/start` 요청 | 슬랙 ID: %s',
            slack_id
        )
        return False

    # 인스턴스 상태 조회
    instance_info_dict = ec2_client.get_instance_info(
        user_owned_instance_list)
    if not instance_info_dict:
        msg = '알 수 없는 이유로 인스턴스 상태 조회에 실패했습니다.'
        slack_client.send_dm(slack_id, msg)

        logging.error('인스턴스 상태 조회 실패 | 인스턴스 ID: %s', user_owned_instance_list)
        return False

    # `stopped` 상태로 만들 인스턴스가 하나라도 있는지 확인
    state_values = []
    for single_info_dict in instance_info_dict.values():
        state_values.append(single_info_dict['instance_state'])

    if not any(value == 'stopped' for value in state_values):
        msg = '이미 모든 인스턴스가 `running` 상태입니다.'
        slack_client.send_dm(slack_id, msg)

        logging.info(
            '`running`으로 상태를 변경할 수 있는 인스턴스가 없는 상황에서의 `/start` 요청 | 인스턴스 상태: %s', instance_info_dict)
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
        slack_client.send_dm(slack_id, msg)

        logging.info(
            '인스턴스 사용 할당량 초과 상태에서 `/start` 요청 | 슬랙 ID: %s',
            slack_id
        )
        return False

    # 인스턴스 시작
    if not ec2_client.start_instance(user_owned_instance_list):
        msg = '알 수 없는 이유로 인스턴스 시작에 실패했습니다.'
        slack_client.send_dm(slack_id, msg)

        logging.error('인스턴스 시작 실패 | 인스턴스 ID: %s', user_owned_instance_list)
        return False

    # 성공 메시지 전송, 로그 데이터 적재
    now = datetime.now(timezone('Asia/Seoul'))
    maximum_usage_time = now + timedelta(
        hours=remaining_tm.hour,
        minutes=remaining_tm.minute,
        seconds=remaining_tm.second
    )
    msg = f'''\
인스턴스를 성공적으로 시작했습니다 🥳
인스턴스를 사용한 다음에는 반드시 `/stop` 명령어로 종료해주세요 ⚠️

- 오늘의 잔여 할당량: `{remaining_tm.hour}시간 {remaining_tm.minute}분 {remaining_tm.second}초`
- 인스턴스 최대 사용 가능 시간: `{maximum_usage_time.strftime('%Y-%m-%d %H:%M:%S')}`

_인스턴스 할당량 초기화는 매일 자정에 진행됩니다._\
    '''

    slack_client.send_dm(slack_id, msg)
    logging.info('인스턴스 시작 | 인스턴스 ID: %s', user_owned_instance_list)

    psql_client.insert_slack_user_request_log(
        student_id,
        'start',
        str(now.strftime('%Y-%m-%d %H:%M:%S'))
    )

    return True


@slack_app.command('/policy')
def handle_policy_command(ack, command) -> bool:
    '''AWS 임시 콘솔 접근 부여 커맨드(/policy)를 처리합니다.'''

    slack_id = command['user_id']
    msg = 'AWS 콘솔 접근 임시 권한을 부여하는 중입니다... 👀'

    ack()
    slack_client.send_dm(slack_id, msg)

    now = datetime.now(timezone('Asia/Seoul'))

    # 교육생 여부 체크
    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)

        assert track == 'DE'
    except TypeError as e:
        msg = '이어드림스쿨 4기 교육생이 아니면 인스턴스의 상태를 조회할 수 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            '교육생이 아닌 슬랙 유저의 `/policy` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False
    except AssertionError as e:
        msg = '현재는 DE 트랙 교육생이 아니면 인스턴스의 상태를 조회할 수 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            'DE 트랙 외 교육생의 `/policy` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False

    policy_reqeust_count = psql_client.get_policy_request_count(
        student_id, now.date())

    if not policy_reqeust_count:
        msg = '데이터를 불러오는 중에 문제가 발생했습니다. 관리자에게 문의해주세요!'

        slack_client.send_dm(slack_id, msg)
        logging.info('`/policy` 요청에서의 DB 접근 오류 | 슬랙 ID: %s', slack_id)

        return False

    if policy_reqeust_count[0][0] >= 4:
        msg = '''\
오늘은 더이상 임시 콘솔 접근 권한을 요청할 수 없습니다.:melting_face:
임시 콘솔 접근 권한은 매일 15분씩 총 4번까지 가능합니다.\
        '''

        slack_client.send_dm(slack_id, msg)
        logging.info(
            '`/policy` 요청 횟수 초과 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False

    def grant_aws_console_access(iam_user_name: str) -> bool:

        if not iam_client.attach_user_policy(iam_user_name, iam_client.STUDENT_POLICY_ARN):
            msg = 'AWS 콘솔 접근 권한 부여 중 문제가 발생하였습니다.:scream: 관리자에게 문의해주세요!'

            slack_client.send_dm(slack_id, msg)
            logging.info(
                '`/policy` 요청에서의 AWS IAM client 호출 오류 | 슬랙 ID: %s', slack_id)

            return False

        msg = '''\
AWS 콘솔 접근을 위한 임시 권한이 부여되었습니다 ✅
지금부터 15분간 AWS 콘솔에 로그인하여 작업할 수 있습니다.\
        '''

        slack_client.send_dm(slack_id, msg)
        psql_client.insert_slack_user_request_log(
            student_id,
            'policy',
            str(now.strftime('%Y-%m-%d %H:%M:%S'))
        )

        return True

    def revoke_aws_console_access() -> bool:
        if not iam_client.detach_user_policy(iam_user_name[0][0], iam_client.STUDENT_POLICY_ARN):
            msg = 'AWS 콘솔 접근 권한 회수 중 문제가 발생하였습니다.:scream: 관리자에게 문의해주세요!'

            slack_client.send_dm(slack_id, msg)
            logging.info(
                '`/policy` 요청에서의 AWS IAM client 호출 오류 | 슬랙 ID: %s', slack_id)

            return False

        msg = f'''\
15분이 경과하여 콘솔 접근 권한이 회수되었습니다 👋
오늘의 콘솔 접근 권한 요청은 총 _{4 - policy_reqeust_count[0][0]}번_ 남았습니다.\
        '''

        slack_client.send_dm(slack_id, msg)

        return True

    iam_user_name = psql_client.get_iam_user_name(student_id)

    if iam_user_name is None:
        msg = 'IAM User 정보를 불러오는 중 문제가 발생했습니다. 관리자에게 문의해주세요!'

        slack_client.send_dm(slack_id, msg)
        logging.info('`/policy` 요청에서의 DB 접근 오류 | 슬랙 ID: %s', slack_id)

        return False

    if len(iam_user_name) == 0:
        msg = 'IAM USER 계정이 부여되지 않은 교육생입니다. 관리자에게 문의해주세요!'

        slack_client.send_dm(slack_id, msg)
        logging.info('IAM 계정이 없는 교육생의 `/policy` 요청 | 슬랙 ID: %s', slack_id)

        return False

    grant_aws_console_access(iam_user_name[0][0])
    policy_timer = threading.Timer(
        900,
        revoke_aws_console_access
    )
    policy_timer.start()

    return True


@slack_app.command('/terminate')
def handle_terminate_command(ack, command) -> bool:
    '''인스턴스 삭제 커멘드(/terminate)를 처리합니다.'''

    ack()

    slack_id = command['user_id']
    text = command['text'].replace(" ", "")
    manager_slack_id = os.getenv('MANAGER_SLACK_ID')

    if len(text) == 0:
        msg = '종료할 인스턴스 아이디를 함께 작성해주세요.'

        slack_client.send_dm(slack_id, msg)

        return False

    request_instance_id = text.split(",")
    terminate_instance = []

    # 교육생 여부 및 트랙 체크
    try:
        track, student_id = psql_client.get_track_and_student_id(slack_id)
        name = psql_client.get_student_name(slack_id)

        assert track == 'DE'
    except TypeError as e:
        msg = '이어드림스쿨 4기 교육생이 아니면 인스턴스를 중지할 수 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            '교육생이 아닌 슬랙 유저의 `/terminate` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False
    except AssertionError as e:
        msg = '현재는 DE 트랙 교육생이 아니면 인스턴스를 중지할 수 없습니다.'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            'DE 트랙 외 교육생의 `/terminate` 요청 | 슬랙 ID: %s | %s',
            slack_id,
            e
        )

        return False

    # 자기 소유 인스턴스 확인
    owned_instances = psql_client.get_user_owned_instance(student_id)

    if owned_instances is None:
        msg = '데이터를 불러오는 중에 문제가 발생했습니다. 관리자에게 문의해주세요!'

        slack_client.send_dm(slack_id, msg)
        logging.info(
            '`/terminate` 요청에서의 DB 연결 오류 | 슬랙 ID: %s', slack_id)

        return False

    for instance in request_instance_id:
        if instance in owned_instances:
            terminate_instance.append(instance)

    if len(terminate_instance) == 0:
        msg = '''\
종료할 인스턴스가 존재하지 않습니다. 👀

콤마(,)로 구분하여 작성했는지 확인해주세요.
자신 소유의 인스턴스가 맞는지 확인해주세요.\
'''

        slack_client.send_dm(slack_id, msg)

        return False

    msg = f'''\
{name[0]} 교육생의 인스턴스 삭제 요청이 있습니다.🔎 삭제 부탁드립니다!

Instance ID : {terminate_instance}\
'''
    slack_client.app.client.chat_postMessage(
        channel=manager_slack_id,
        text=msg
    )

    msg = f'''\
인스턴스 {terminate_instance}의 삭제 요청을 보냈습니다... 🗑️\
'''
    slack_client.app.client.chat_postMessage(
        channel=slack_id,
        text=msg
    )


@app.route('/slack/events', methods=['POST'])
def handle_slack_events():
    '''슬랙에서 송신된 이벤트 관련 request를 처리합니다.'''

    return slack_req_handler.handle(request)
