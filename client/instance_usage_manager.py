'''인스턴스 사용량을 관리하는 모듈'''


import os
from datetime import datetime, timedelta

import holidays
from pytz import timezone


class InstanceUsageManager:
    '''인스턴스의 사용량을 관리하고 일별 사용 한도와 공휴일을 고려하여 사용량을 추적하는 클래스.'''

    def __init__(self) -> None:
        self.today_date = datetime.now(timezone('Asia/Seoul'))
        self.midnight_time = datetime.combine(
            self.today_date,
            datetime.min.time()
        ).astimezone(timezone('Asia/Seoul'))
        self.throshold_time = self.get_threshold_time()
        # self.timer = InstanceUsageManager()  # TODO

    def get_threshold_time(self) -> timedelta:
        '''공휴일과 주말을 기준으로 인스턴스의 일별 할당 시간을 계산.'''

        year = self.today_date.year
        kr_holidays = holidays.country_holidays('KR', years=year)

        if self.today_date in kr_holidays or self.today_date.weekday() >= 5:
            threshold_time = 12
        else:
            threshold_time = 6

        return timedelta(hours=threshold_time)

    def insert_system_logs(self, instance_id: str, log_type: str) -> None:
        '''system log를 DB에 저장하는 기능 구현.'''

        with psycopg.connect(  # pylint: disable=not-context-manager
            host=os.getenv('AWS_MANAGER_DB'),
            dbname=os.getenv('AWS_MANAGER_DB_NAME'),
            user=os.getenv('AWS_MANAGER_DB_USER'),
            password=os.getenv('AWS_MANAGER_DB_USER_PW'),
        ) as conn:
            with conn.cursor() as cur:
                query = '''
                    INSERT INTO
                        system_instance_log(
                            instance_id
                            , log_type
                            , log_time)
                    VALUES
                        (%s, %s, %s)
                    ;
                    '''
                cur.execute(query, (instance_id, log_type, str(
                    datetime.now(timezone('Asia/Seoul')))))
                conn.commit()

    def get_today_instance_logs(self, instance_id) -> list[tuple]:
        '''지정된 인스턴스 ID에 대해 오늘의 로그를 데이터베이스에서 조회하여 반환.
        로그는 'slack_instance_request_log'와 'system_instance_log' 두 테이블에서 조회함.
        '''

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
                        ,request_type
                        ,request_time
                    FROM
                        slack_instance_request_log
                    WHERE
                        instance_id = %s
                        AND request_time::DATE = CURRENT_DATE
                    UNION
                    SELECT
                        instance_id
                        ,log_type
                        ,log_time
                    FROM
                        system_instance_log
                    WHERE
                        instance_id = %s
                        AND log_time::DATE = CURRENT_DATE
                    ORDER BY
                        request_time
                    ;
                    '''

                cur.execute(query, (instance_id, instance_id))
                logs = cur.fetchall()

        return logs

    def calculate_instance_usage(self, instance_id) -> timedelta:
        '''오늘의 Log들을 통해 총 instance 사용 시간 계산'''

        logs = self.get_today_instance_logs(instance_id)
        total_usage_time = timedelta()

        for idx, log in enumerate(logs[::2]):
            start_time = log[-1]

            try:
                stop_time = logs[idx*2 + 1][-1]
                usage_time = stop_time - start_time
            except IndexError:
                usage_time = datetime.now() - start_time

            total_usage_time += usage_time

        return total_usage_time

    def get_remaining_time(self, instance_id):
        '''일별 한도를 기준으로 인스턴스의 남은 사용 시간을 계산.'''

        total_usage_time = self.calculate_instance_usage(instance_id)

        return self.throshold_time - total_usage_time

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

    def stop_quota_exceeded_instance(self):
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
