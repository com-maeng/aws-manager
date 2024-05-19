import os

from slack_bolt import App


app = App(
    token=os.getenv('AWS_MANAGER_SLACK_BOT_TOKEN'),
    signing_secret=os.getenv('AWS_MANAGER_SLACK_SIGNING_SECRET'),
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


@app.command('/start')
def handle_start_command(ack, command):
    '''인스턴스 시작 커맨드(/start) 처리.

    Args:
        ack: `ack()` utility function, which returns acknowledgement to the Slack servers.
        command: An alias for payload in an `@app.command` listener.
    '''

    ack()

    user_id = command['user_id']
    user_text = command['text']

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


if __name__ == '__main__':
    app.start(port=int(os.getenv('AWS_MANAGER_DEV_SLACK_PORT')))
