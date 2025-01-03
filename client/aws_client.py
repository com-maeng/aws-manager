'''AWS API를 활용하는 작업에 대한 인터페이스입니다.'''


import os
import logging
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError


class EC2Client:
    '''메인 EC2 클라이언트입니다.'''

    def __init__(self):
        self.client = boto3.client(
            'ec2',
            aws_access_key_id=os.getenv('AWS_MANAGER_AWS_ACCESS_KEY'),
            aws_secret_access_key=os.getenv(
                'AWS_MANAGER_AWS_SECRET_ACCESS_KEY'),
            region_name='ap-northeast-2',
        )

    def get_instance_info(
        self,
        instance_ids: list[str]
    ) -> Optional[dict[str, dict[str, str]]]:
        '''AWS API를 호출하여 인스턴스 state, Name 태그 정보 등을 반환합니다.

        Returns:
          각 인스턴스에 대응되는 다양한 정보들이 key-value 형태로 저장됩니다.
          예시는 아래와 같습니다.

          {
            'i-123456789': {
                'instance_state': 'stopped',
                'name': 'hongju-spark-master1',
                'public_ip_address': '34.1.2.3',
                'private_ip_address': '10.0.0.2'
            },
            'i-987651231': {
                'instance_state': 'running',
                'name': 'hongju-spark-master2',
                'public_ip_address': '34.1.2.4',
                'private_ip_address': '10.0.0.3'
            }
          }
        '''

        try:
            resp_dict = self.client.describe_instances(
                InstanceIds=instance_ids
            )
        except ClientError as e:
            logging.error(
                '인스턴스 상태, Name 태그 정보 API 호출 실패: %s | 인스턴스 ID 목록: %s',
                instance_ids,
                e
            )

            return None

        instance_state_name_dict = {}

        for reservation in resp_dict['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                state = instance['State']['Name']
                name_tag_value = None
                public_ip = None
                private_ip = None

                # 'Name' 태그 값 파싱
                try:
                    for tag in instance['Tags']:
                        if 'Name' in tag.values():
                            name_tag_value = tag['Value']
                            break
                except KeyError:
                    logging.info('인스턴스에 태그가 없음 (`Tags`): %s', instance.keys())

                # Public IP 주소값 파싱
                try:
                    public_ip = instance['PublicIpAddress']
                except KeyError:
                    logging.info(
                        '인스턴스에 Public IP 주소가 없음 (`Tags`): %s', instance.keys())

                # Private IP 주소값 파싱
                try:
                    private_ip = instance['PrivateIpAddress']
                except KeyError:
                    logging.info(
                        '인스턴스에 Private IP 주소가 없음 (`Tags`): %s', instance.keys())

                # 파싱 정보 할당
                instance_state_name_dict[instance_id] = {
                    'instance_state': state,
                    'name': name_tag_value,
                    'public_ip_address': public_ip,
                    'private_ip_address': private_ip
                }

        return instance_state_name_dict

    def start_instance(
        self,
        instance_ids: list[str]
    ) -> bool:
        '''EC2 인스턴스를 시작합니다.'''

        try:
            self.client.start_instances(
                InstanceIds=instance_ids,
                DryRun=False
            )

            return True
        except ClientError as e:
            logging.error(
                '인스턴스 시작 API (`start_instances()`) 호출 실패 | 인스턴스 ID: %s | %s',
                instance_ids,
                e
            )

            return False

    def stop_instance(
        self,
        instance_ids: list[str]
    ) -> bool:
        '''EC2 인스턴스를 중지합니다.'''

        try:
            self.client.stop_instances(
                InstanceIds=instance_ids,
                DryRun=False
            )

            return True
        except ClientError as e:
            logging.error(
                '인스턴스 중지 API (`stop_instances()`) 호출 실패 | 인스턴스 ID: %s | %s',
                instance_ids,
                e
            )

            return False

    def get_live_instance_id_list(self, state: list[str]) -> list[str]:
        '''시작/중지 상태인 모든 EC2 인스턴스의 ID가 담긴 리스트를 반환합니다.'''

        instance_id_list = []
        response = self.client.describe_instances(Filters=[
            {
                'Name': 'instance-state-name',
                'Values': state,
            },
        ])
        reservations = response['Reservations']

        for reservation in reservations:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                instance_id_list.append(instance_id)

        return instance_id_list

    def allocate_eip_address(self, number_of_instance: int) -> list[str]:
        '''인스턴스의 갯수만큼 EIP 주소를 생성합니다.'''

        allocation_id_list = []

        for _ in range(number_of_instance):
            try:
                resp = self.client.allocate_address(
                    TagSpecifications=[
                        {
                            'ResourceType': "elastic-ip",
                            'Tags': [
                                {
                                    'Key': 'Name',
                                    'Value': 'EIP for EC2 instance'
                                },
                            ],
                        },
                    ]
                )

                allocation_id_list.append(resp['AllocationId'])
            except ClientError as e:
                logging.error(
                    'EIP allocation API(`allocate_address()`) 호출 실패 | %s',
                    e
                )

        return allocation_id_list

    def associate_eip_address(
        self,
        instance_id_list: list[str],
        allocation_id_list: list[str],
    ) -> None:
        '''생성된 EIP 주소를 모든 인스턴스에 하나씩 할당합니다.'''

        for instance_id, allocation_id in zip(instance_id_list, allocation_id_list):
            try:
                self.client.associate_address(
                    AllocationId=allocation_id,
                    InstanceId=instance_id
                )
            except ClientError as e:
                logging.error(
                    'EIP associate API(`associate_address()`) 호출 실패 | \
`AllocationId`: %s | `InstanceId`: %s | %s',
                    allocation_id,
                    instance_id,
                    e
                )


class IAMClient:
    '''IAM API를 활용하는 작업을 처리합니다.'''

    def __init__(self):
        self.client = boto3.client(
            'iam',
            aws_access_key_id=os.getenv('AWS_MANAGER_AWS_ACCESS_KEY'),
            aws_secret_access_key=os.getenv(
                'AWS_MANAGER_AWS_SECRET_ACCESS_KEY'),
            region_name='ap-northeast-2',
        )
        self.STUDENT_POLICY_ARN = os.getenv(  # pylint: disable=invalid-name
            'AWS_MANAGER_AWS_STUDENT_POLICY_ARN')
        self.STUDENT_GROUP_NAME = 'student'  # pylint: disable=invalid-name

    def detach_policy_from_group(
            self,
            group_name: str,
            policy_arn: str,
    ) -> None:
        '''IAM 그룹에서 특정 정책을 제거합니다.'''

        try:
            self.client.detach_group_policy(
                GroupName=group_name,
                PolicyArn=policy_arn,
            )
        except ClientError as e:
            logging.error(
                'IAM 그룹 정책 제거 API(`detach_group_policy()`) 호출 실패 | %s',
                e,
            )
            raise e

    def attach_policy_to_group(
            self,
            group_name: str,
            policy_arn: str,
    ) -> None:
        '''IAM 그룹에 특정 정책을 추가합니다.'''

        try:
            self.client.attach_group_policy(
                GroupName=group_name,
                PolicyArn=policy_arn,
            )
        except ClientError as e:
            logging.error(
                'IAM 그룹 정책 부여 API(`attach_group_policy()`) 호출 실패 | %s',
                e,
            )
            raise e

    def attach_user_policy(
        self,
        user_name: str,
        policy_arn: str,
    ) -> bool:
        '''IAM user에게 특정 정책을 추가합니다.'''

        try:
            self.client.attach_user_policy(
                UserName=user_name,
                PolicyArn=policy_arn,
            )

            return True
        except ClientError as e:
            logging.error(
                'IAM 유저 정책 부여 API(`attach_user_policy()`) 호출 실패 | %s',
                e,
            )

            return False

    def detach_user_policy(
        self,
        user_name: str,
        policy_arn: str,
    ) -> bool:
        '''IAM user에게 특정 정책을 제거합니다.'''

        try:
            self.client.detach_user_policy(
                UserName=user_name,
                PolicyArn=policy_arn,
            )

            return True
        except ClientError as e:
            logging.error(
                'IAM 유저 정책 제거 API(`detach_user_policy()`) 호출 실패 | %s',
                e,
            )

            return False


class CloudTrailClient:
    '''AWS CloudTrail API를 활용하는 작업을 모두 구현합니다.'''

    def __init__(self):
        self.client = boto3.client(
            'cloudtrail',
            aws_access_key_id=os.getenv('AWS_MANAGER_AWS_ACCESS_KEY'),
            aws_secret_access_key=os.getenv(
                'AWS_MANAGER_AWS_SECRET_ACCESS_KEY'),
            region_name='ap-northeast-2',
        )

    def get_event_log_by_event_name(
        self,
        event_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[list[dict]]:
        ''' 지정된 시간 범위에 생성된 CloudTrail 로그들 중 해당 event name에 알맞은 log들을 추출합니다.

        Args:
            event_name (str): AWS CloudTrail Event history의 Event name 입니다.
            start_time (datetime): 조회 시작 시간으로 UTC 기준 시간이 들어와야 log를 정확하게 추출합니다. 
            end_time (datetime): 조회 종료 시간으로 UTC 기준 시간이 들어와야 log를 정확하게 추출합니다. 
        '''

        event_logs = []

        try:
            response = self.client.lookup_events(
                LookupAttributes=[
                    {
                        'AttributeKey': 'EventName',
                        'AttributeValue': event_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                MaxResults=50,
            )
        except ClientError as e:
            logging.error(
                'CloudTrail의 이벤트 이름 %s에 대한 이벤트 조회 실패 | %s',
                event_name,
                e,
            )

            return None

        event_logs.extend(response['Events'])

        while 'NextToken' in response.keys():
            try:
                response = self.client.lookup_events(
                    LookupAttributes=[
                        {
                            'AttributeKey': 'EventName',
                            'AttributeValue': event_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    MaxResults=50,
                    NextToken=response['NextToken']
                )
            except ClientError as e:
                logging.error(
                    'CloudTrail의 이벤트 이름 %s에 대한 이벤트 조회 실패 | %s',
                    event_name,
                    e,
                )

                return None

            event_logs.extend(response['Events'])

        return event_logs
