'''슬랙 API를 활용하는 작업에 대한 인터페이스입니다.'''


import os

from slack_bolt import App


class SlackClient:
    '''메인 클라이언트입니다.'''

    def __init__(self) -> None:
        self.app = App(
            token=os.getenv('AWS_MANAGER_SLACK_BOT_TOKEN'),
            signing_secret=os.getenv('AWS_MANAGER_SLACK_SIGNING_SECRET'),
        )
        self.de_group_id = os.getenv('AWS_MANAGER_SLACK_DE_GROUP_ID')
        self.ds_group_id = os.getenv('AWS_MANAGER_SLACK_DS_GROUP_ID')

    def get_users_info_from_group(self, track: str) -> list[dict[str, str]]:
        '''특정 트랙에 속하는 사용자들의 정보를 반환합니다.'''

        if track == 'DE':
            group_id = self.de_group_id
        elif track == 'DS':
            group_id = self.ds_group_id

        resp = self.app.client.usergroups_users_list(usergroup=group_id)
        users_id = resp.data['users']
        users_info = []

        for user_id in users_id:
            user_info = self.app.client.users_info(user=user_id)

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
