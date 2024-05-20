import os

from slack_bolt import App
import boto3
from botocore.exceptions import ClientError

app = App(
    token=os.getenv('AWS_MANAGER_SLACK_BOT_TOKEN'),
    signing_secret=os.getenv('AWS_MANAGER_SLACK_SIGNING_SECRET'),
)

# ec2
ec2 = boto3.client(
    'ec2',
    aws_access_key_id=os.getenv('INSTANCE_MANAGER_AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('INSTANCE_MANAGER_AWS_SECRET_ACCESS_KEY'),
    region_name="ap-northeast-2"
)


def get_track(user_id: str):
    '''사용자의 트랙 정보를 반환.
    '''

    ...


def get_instance_state(instance_id: str):
    '''인스턴스의 상태 정보를 반환.
    '''

    ...


def get_remaining_instance_limit(user_id: str):
    '''사용자의 잔여 인스턴스 사용 가능 시간을 반환.
    '''

    ...


def start_instance(instance_id: str):
    '''인스턴스를 시작.
    '''

    ...


def instance_management(status, user_instance_id):
    '''
    인스턴스 시작 혹은 종료 커맨드 사용시, 인스턴스 처리(시작 및 종료).
    만약, 존재하지 않는 instance_id 일 때, error 처리 
    '''

    try:
        if status == "start":
            ec2.start_instances(InstanceIds=[user_instance_id], DryRun=False)
        elif status == "end":
            ec2.stop_instances(InstanceIds=[user_instance_id], DryRun=False)
        return True
    except ClientError:
        return False


@app.command('/start')
def handle_start_command(ack, say, command):
    '''인스턴스 시작 커맨드(/start) 처리.

    Args:
        ack: `ack()` utility function, which returns acknowledgement to the Slack servers.
        command: An alias for payload in an `@app.command` listener.
    '''

    ack()

    user_name = command['user_name']
    user_id = command['user_id']
    instance_id = command['text']

    # ec2 시작
    flag_instance = instance_management('start', instance_id)

    # ec2 확인후 응답
    if flag_instance:
        say(f"{user_name}님의 {instance_id}의 인스턴스를 시작합니다")
    else:
        say("옳지 않은 인스턴스 ID입니다. 다시 확인해서 작성해주세요")

    if get_track(user_id) != 'DE':
        ...

    # instance_id = user_text.split()[-1]  # 인스턴스 ID가 가장 마지막에 위치한다고 가정

    # if get_instance_state(instance_id) != 'Stopped':
    #     ...

    # if get_remaining_instance_limit(user_id) <= 0:
    #     ...

    # respond(f'[{instance_id}] 인스턴스를 시작 중입니다.')

    # if not start_instance(instance_id):
    #     respond(f'[{instance_id}] 인스턴스 시작에 실패했습니다.') # TODO: 사유 설명 추가
    #     return False  # TODO: 리턴값 조정

    # TODO: 금일 잔여량, 시작시간, 예정 종료 시간 정보 전송

    # TODO: 로그 적재


@app.command('/end')
def handle_end_command(ack, say, command):
    '''인스턴스 시작 커맨드(/end) 처리.

    Args:
        ack: `ack()` utility function, which returns acknowledgement to the Slack servers.
        command: An alias for payload in an `@app.command` listener.
    '''

    ack()

    user_name = command['user_name']
    instance_id = command['text']

    # ec2 시작
    flag_instance = instance_management('end', instance_id)

    # ec2 확인후 응답
    if flag_instance:
        say(f"{user_name}님의 {instance_id}의 인스턴스를 종료합니다")
    else:
        say("옳지 않은 인스턴스 ID입니다. 다시 확인해서 작성해주세요")


if __name__ == '__main__':
    app.start(port=int(os.getenv('AWS_MANAGER_DEV_SLACK_PORT')))
