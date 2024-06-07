'''자정마다 실행시킬 상태 반영 로직 구현하는 모듈.'''


from instance_police import InstancePolice


def insert_log_at_midnight():
    '''자정마다 사용중인 인스턴스들을 system log에 적재 기능 구현.'''

    instance_police = InstancePolice()

    running_instance = instance_police.get_instance_running_list()

    for instance_id in running_instance:
        instance_police.timer.insert_system_logs(instance_id, 'start')


if __name__ == "__main__":

    insert_log_at_midnight()
