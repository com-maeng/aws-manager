'''Insert instance data from slack to the `instance_info` table.
'''
import os

import psycopg
import boto3


def get_instance_info(ec2: boto3.client) -> list[str]:  # pylint: disable=redefined-outer-name
    '''aws ec2 인스턴스 정보를 가져옵니다.
    '''

    instance_info = []
    reservations = ec2.describe_instances()['Reservations']

    for res in reservations:

        instance_info.append(
            [res['Instances'][0]['InstanceId'], res['Instances'][0]['State']['Name']])

    return instance_info


def insert_instance_info(instance_info_list: list) -> None:  # pylint: disable=not-context-manager
    '''인스턴스 정보들을 instance_info 테이블에 삽입합니다.
    '''
    with psycopg.connect(
        host=os.getenv('AWS_MANAGER_DEV_DB'),
        dbname=os.getenv('AWS_MANAGER_DEV_DB_NAME'),
        user=os.getenv('AWS_MANAGER_DEV_DB_USER'),
        password=os.getenv('AWS_MANAGER_DEV_DB_USER_PW'),
    ) as conn:
        with psycopg.ClientCursor(conn) as cur:
            args = ','.join(cur.mogrify("(%s,%s)", i)
                            for i in instance_info_list)

            cur.execute(
                "INSERT INTO instance_info (instance_id, state) VALUES " + (args))
            conn.commit()


if __name__ == '__main__':
    ec2 = boto3.client(
        'ec2',
        aws_access_key_id=os.getenv('INSTANCE_MANAGER_AWS_ACCESS_KEY'),
        aws_secret_access_key=os.getenv(
            'INSTANCE_MANAGER_AWS_SECRET_ACCESS_KEY'),
        region_name="ap-northeast-2"
    )

    instance_id_state = get_instance_info(ec2)
    insert_instance_info(instance_id_state)
