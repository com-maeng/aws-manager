'''PostgreSQL과의 상호작용이 필요한 작업에 대한 인터페이스입니다.'''


import os
import logging
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
    ) -> list[Optional[tuple]]:
        fetched_data = []

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
                        fetched_data = cur.fetchall()
        except psycopg.Error as e:
            logging.error('쿼리 실행 실패 | %s', e)

            raise e

        return fetched_data

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
    ) -> tuple[Optional[str], Optional[str]]:
        '''사용자의 정보를 반환합니다.'''

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

        fetched_data = self._execute_query(query, (slack_id,))

        if fetched_data:
            return fetched_data

    def insert_instance_request_log(
        self,
        student_id: str,
        instance_id: str,
        request_type: str,
        request_time: str
    ) -> None:
        '''인스턴스 시작/중지 요청 로그를 저장합니다.'''

        query = '''
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
        self._execute_query(
            query,
            (student_id, instance_id, request_type, request_time)
        )

    def get_latest_started_instance_id(self, student_id) -> Optional[str]:
        '''사용자가 가장 최근에 시작(`/start`) 요청을 한 인스턴스의 ID를 반환합니다.

        당일 시작 요청에 대한 로그만을 조회합니다.
        '''

        query = '''
            SELECT 
                instance_id
            FROM 
                slack_instance_request_log
            WHERE 
                request_type = 'start'
                AND student_id = %s
            ORDER BY
                request_time DESC 
            LIMIT
                1
            ;
        '''
        fetched_data = self._execute_query(query, (student_id,))

        if fetched_data:
            return fetched_data[0]  # Single value tuple

        return ''

    def insert_into_ownership(
            self,
            owner_info_list: list[tuple]
    ) -> None:
        '''사용자의 instance 소유 정보를 DB에 저장합니다.'''

        query = '''
            INSERT INTO
                ownership_info (
                    iam_username
                    , instance_id
                )
            VALUES
                (%s, %s)
            ;
        '''

        self._execute_query(query, (owner_info_list,), many=True)

    def check_existed_instance_id(
            self,
            instance_id_list: list
    ) -> list[tuple]:
        '''주어진 인스턴스가 DB에 적재되어 있는지 확인합니다.'''

        query = '''
            SELECT
                iam_username
                , instance_id
            FROM
                ownership_info
            WHERE
                instance_id = ANY(%s)
            ;
        '''

        fetched_data = self._execute_query(query, (instance_id_list,))

        return fetched_data
