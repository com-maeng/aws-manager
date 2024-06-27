'''PostgreSQL과의 상호작용이 필요한 작업에 대한 인터페이스입니다.'''


import os
import logging
from datetime import datetime, time
from typing import Optional

import psycopg


class PSQLClient:
    '''메인 클라이언트입니다.'''

    def __init__(self) -> None:
        self.host = os.getenv('AWS_MANAGER_DB_HOST')
        self.dbname = os.getenv('AWS_MANAGER_DB_NAME')
        self.user = os.getenv('AWS_MANAGER_DB_USER')
        self.password = os.getenv('AWS_MANAGER_DB_PW')

    def _execute_query(
        self,
        query: str,
        params: tuple = None,
        many: bool = False
    ) -> Optional[list[tuple[str]]]:
        try:
            with psycopg.connect(  # pylint: disable=not-context-manager
                host=self.host,
                dbname=self.dbname,
                user=self.user,
                password=self.password
            ) as conn:
                with conn.cursor() as cur:
                    if many:
                        # tuple -> list
                        cur.executemany(query, list(params[0]))
                    else:
                        cur.execute(query, params)

                    if query.split()[0] == 'SELECT':
                        return cur.fetchall()
        except psycopg.Error as e:
            logging.error('쿼리 실행 실패 | query: %s | error: %s', query, e)

    def insert_into_student(
        self,
        users_info: list[dict[str, str]],
    ) -> None:
        '''Insert student user data to the `student` table.'''

        query = '''
            INSERT INTO
                student (name, slack_id, track, email)
            VALUES
                (%(name)s, %(slack_id)s, %(track)s, %(email)s)
            ;
        '''

        self._execute_query(query, (users_info,), many=True)

    def get_track_and_student_id(
        self,
        slack_id: str
    ) -> Optional[tuple[str, int]]:
        '''슬랙 유저의 트랙과 `student` 테이블의 ID 정보를 반환합니다.'''

        query = '''
            SELECT
                track
                , student_id
            FROM
                student
            WHERE
                slack_id = %s
            ;
        '''

        fetched_data = self._execute_query(query, (slack_id,))

        if fetched_data:
            return fetched_data[0]

    def insert_slack_user_request_log(
        self,
        student_id: int,
        request_type: str,
        request_time: str
    ) -> None:
        '''슬랙 커맨드가 정상적으로 처리되었을 때, 해당 로그를 DB에 저장합니다.'''

        query = '''
            INSERT INTO
                slack_user_request_log (
                    request_user
                    , request_type
                    , request_time
                )
            VALUES
                (%s, %s, %s)
            ;
        '''
        self._execute_query(
            query,
            (student_id, request_type, request_time)
        )

    def get_latest_started_instance_id(
        self,
        student_id
    ) -> Optional[str]:
        '''사용자가 가장 최근에 시작(`/start`) 요청을 한 인스턴스의 ID를 반환합니다.

        당일 시작 요청에 대한 로그만을 조회합니다.
        '''

        query = '''
            SELECT
                instance_id
            FROM
                slack_user_request_log
            WHERE
                request_type = 'start'
                AND request_user = %s
            ORDER BY
                request_time DESC
            LIMIT
                1
            ;
        '''
        fetched_data = self._execute_query(query, (student_id,))

        if fetched_data:
            return fetched_data[0][0]

        return None

    def insert_into_ownership_info(
        self,
        owner_info_list: list[tuple[int, str]]
    ) -> None:
        '''사용자의 instance 소유 정보를 DB에 저장합니다.'''

        query = '''
            INSERT INTO
                ownership_info (
                    owned_by
                    , instance_id
                )
            VALUES
                (%s, %s)
            ON 
                CONFLICT (instance_id) 
            DO 
                NOTHING
        '''

        self._execute_query(query, (owner_info_list,), many=True)

    def check_existed_instance_id(
        self,
        instance_id_list: list[str]
    ) -> list[tuple[str, str]]:
        '''주어진 인스턴스가 DB에 적재되어 있는지 확인합니다.'''

        query = '''
            SELECT
                owner
                , instance_id
            FROM
                ownership_info
            WHERE
                instance_id = ANY(%s)
            ;
        '''

        fetched_data = self._execute_query(query, (instance_id_list,))

        return fetched_data

    def get_user_owned_instance(
        self,
        student_id: str
    ) -> Optional[list[str]]:
        '''특정 사용자 소유의 모든 인스턴스에 대한 ID를 반환합니다.'''

        query = '''
            SELECT
                instance_id
            FROM
                ownership_info
            WHERE
                owned_by = (
                    SELECT
                        user_id
                    FROM
                        iam_user
                    WHERE
                        owned_by = %s
                )
            ;
        '''
        fetched_data = self._execute_query(query, (student_id,))

        if fetched_data:
            instance_id_list = []

            for d in fetched_data:
                instance_id_list.append(d[0])  # `instance_id`

            return instance_id_list

    def get_today_instance_logs(
        self,
        instance_id: str
    ) -> list[tuple[str, str]]:
        '''지정된 인스턴스 ID에 대해 오늘의 로그를 DB에서 조회하여리스트로 반환합니다.

        로그는 'slack_user_request_log'와 'system_log' 두 테이블에서 조회함.
        '''

        query = '''
            SELECT
                instance_id
                ,request_type
                ,request_time
            FROM
                slack_user_request_log
            WHERE
                instance_id = %s
                AND request_time::DATE = CURRENT_DATE
            UNION
            SELECT
                instance_id
                ,log_type
                ,log_time
            FROM
                system_log
            WHERE
                instance_id = %s
                AND log_time::DATE = CURRENT_DATE
            ORDER BY
                request_time
            ;
        '''

        return self._execute_query(query, (instance_id, instance_id))

    def get_student_owned_instances(
        self,
        student_id: str
    ) -> list[tuple[str, int]]:
        '''특정 학생이 소유하고 있는 인스턴스의 리스트를 반환합니다.'''

        query = '''
            SELECT
                instance_id
            FROM
                ownership_info
            WHERE
                owner = (
                    SELECT
                        iam_username,
                    FROM
                        student
                    WHERE
                        student_id = %s
                )
            ;
        '''

        return self._execute_query(query, (student_id,))

    def get_slack_id_by_instance(
        self,
        instance_id: str
    ) -> list[tuple[str, str]]:
        '''해당 인스턴스 id를 가지고 있는 학생의 slack id의 값을 반환합니다.'''

        query = '''
            SELECT
                slack_id
            FROM
                student
            WHERE
                iam_username = (
                    SELECT
                        owner
                    FROM
                        ownership_info
                    WHERE
                        instance_id = %s
                )
            ;
        '''

        fetched_data = self._execute_query(query, (instance_id,))

        if fetched_data:
            return fetched_data[0][0]

        return None

    def get_name_and_student_id(self) -> list[tuple[str, int]]:
        '''student 테이블에 적재된 모든 학생들의 한글 본명과 ID를 반환합니다.'''

        query = '''
            SELECT
                name  -- 한글 본명
                , student_id
            FROM
                student
            ;
        '''

        fetched_data = self._execute_query(query)

        return fetched_data

    def insert_into_iam_user(
        self,
        iam_user_data: list[tuple[str, int]]
    ) -> None:
        '''iam_user 테이블에 데이터를 적재합니다.'''

        query = '''
            INSERT INTO
                iam_user (user_name, owned_by)
            VALUES
                (%s, %s)
            ;
        '''

        self._execute_query(query, (iam_user_data, ), many=True)

    def insert_into_cloudtrail_log(
        self,
        logs: list[tuple[str, str, datetime]]
    ) -> None:
        '''CloudTrail의 로그를 적재합니다.'''

        query = '''
            INSERT INTO
                cloudtrail_log (instance_id, log_type, log_time)
            VALUES
                (%s, %s, %s)
            ON 
                CONFLICT (instance_id, log_type, log_time) 
            DO 
                NOTHING
            ;
        '''

        self._execute_query(query, (logs, ), many=True)

    def get_remaining_usage_time(
        self,
        student_id: str
    ) -> time:
        '''사용자의 잔여 인스턴스 사용 할당량을 반환합니다.'''

        query = '''
            SELECT
                remaining_time
            FROM
                ec2_usage_quota
            WHERE
                iam_user_id = (
                    SELECT
                        user_id
                    FROM
                        iam_user
                    WHERE
                        owned_by = %s
                )
            ;
        '''
        ret = self._execute_query(query, (student_id,))
        remaining_tm = ret[0][0]

        return remaining_tm

    def get_iam_user(self) -> Optional[list[tuple]]:
        '''iam_user table에 있는 데이터를 추출합니다.'''

        query = '''
            SELECT 
                user_name
                , user_id
            FROM
                iam_user
            ;
        '''

        fetched_data = self._execute_query(query)

        return fetched_data

    def get_slack_id_and_instance_id_with_no_remaining_time(
        self
    ) -> Optional[list[tuple[str, str]]]:
        '''ec2 사용시간을 모두 사용한 학생의 슬랙 아이디, 소유한 인스턴스들을 추출합니다.'''

        query = '''
            SELECT 
                s.slack_id, oi.instance_id
            FROM 
                student AS s
            JOIN 
                iam_user AS iu ON s.student_id = iu.owned_by
            JOIN 
                ownership_info AS oi ON iu.user_id = oi.owned_by
            JOIN 
                ec2_usage_quota AS euq ON iu.user_id = euq.iam_user_id
            WHERE 
                euq.remaining_time = '00:00:00'
            ;
        '''

        fetched_data = self._execute_query(query)

        return fetched_data

    def get_iam_user_name(
        self,
        student_id: int
    ) -> Optional[list[tuple[str]]]:
        '''iam_user table 에서 user_name을 반환합니다.'''

        query = '''
            SELECT
                user_name
            FROM
                iam_user
            WHERE
                owned_by = %s
            ;
        '''

        fetched_data = self._execute_query(query, (student_id,))

        return fetched_data

    def get_policy_request_count(
        self,
        student_id: int,
        date: datetime
    ) -> Optional[int]:
        '''사용자가 오늘 요청한 (`/policy`) 횟수를 반환합니다.'''

        query = '''
            SELECT 
                COUNT(*)
            FROM 
                slack_user_request_log
            WHERE 
                request_type = 'policy'
                AND request_user = %s
                AND request_time::DATE = %s
            ;
        '''

        fetched_data = self._execute_query(query, (student_id, date))

        return fetched_data
