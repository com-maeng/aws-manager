'''Insert student user data from slack to the `student` table.
'''


import os

import psycopg
from slack_bolt import App


def get_users_id_from_group(app: App, group_id: str) -> list[str]:  # pylint: disable=redefined-outer-name
    '''유저 그룹에 속하는 유저들의 ID 목록을 반환합니다.
    '''

    resp = app.client.usergroups_users_list(usergroup=group_id)

    return resp.data['users']


def get_users_info(app: App, users_id_list: list[str], track: str) -> list[dict[str, str]]:  # pylint: disable=redefined-outer-name
    '''사용자 ID를 활용하여 슬랙 정보를 가져옵니다.
    '''

    users_info = []

    for user_id in users_id_list:
        user_info = app.client.users_info(user=user_id)
        display_name = user_info.data['user']['profile']['display_name']
        real_name = display_name.split('_')[0]
        email = user_info.data['user']['profile']['email']

        users_info.append(
            {
                'name': real_name,
                'slack_id': user_id,
                'track': track,
                'email': email
            }
        )

    return users_info


def insert_info(users_info: list[list[dict[str, str]]]):
    '''사용자 정보를 `student` 테이블에 삽입합니다.
    '''

    with psycopg.connect(  # pylint: disable=not-context-manager
        host=os.getenv('AWS_MANAGER_DB_HOST'),
        dbname=os.getenv('AWS_MANAGER_DB_NAME'),
        user=os.getenv('AWS_MANAGER_DB_USER'),
        password=os.getenv('AWS_MANAGER_DB_PW'),
    ) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                '''
                INSERT INTO
                    student (name, slack_id, track, email)
                VALUES
                    (%(name)s, %(slack_id)s, %(track)s, %(email)s)
                ''',
                users_info
            )

            conn.commit()


if __name__ == '__main__':
    app = App(
        token=os.getenv('AWS_MANAGER_SLACK_BOT_TOKEN'),
        signing_secret=os.getenv('AWS_MANAGER_SLACK_SIGNING_SECRET'),
    )

    de_users_id = get_users_id_from_group(
        app, os.getenv('AWS_MANAGER_SLACK_DE_GROUP_ID'))
    ds_users_id = get_users_id_from_group(
        app, os.getenv('AWS_MANAGER_SLACK_DS_GROUP_ID'))

    de_users_info = get_users_info(app, de_users_id, 'DE')
    ds_users_info = get_users_info(app, ds_users_id, 'DS')

    insert_info(de_users_info + ds_users_info)
