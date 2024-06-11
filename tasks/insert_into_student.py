'''슬랙에서 사용자별 정보를 불러와 `student` 테이블에 적재합니다.'''


import os
import sys


current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(app_dir)

if __name__ == '__main__':
    from client.slack_client import SlackClient
    from client.psql_client import PSQLClient

    slack_client = SlackClient()
    db_client = PSQLClient()

    de_users_info = slack_client.get_users_info_from_group('DE')
    ds_users_info = slack_client.get_users_info_from_group('DS')

    db_client.insert_into_student(de_users_info + ds_users_info)
