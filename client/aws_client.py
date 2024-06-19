'''AWS API를 활용하는 작업에 대한 인터페이스입니다.'''


import os
import logging
from datetime import datetime
from typing import Optional, List

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

    def get_instance_state(self, instance_id: Optional[str]) -> str:
        '''Get the current state of the EC2 instance.'''

        try:
            resp = self.client.describe_instances(InstanceIds=[instance_id])
            state = resp['Reservations'][0]['Instances'][0]['State']['Name']

            return state
        except ClientError as e:
            logging.error(
                '인스턴스 상태 정보 API 호출 실패 | 인스턴스 ID: %s | %s',
                instance_id,
                e
            )

            return ''

    def start_instance(self, instance_id: str) -> None:
        '''Start the EC2 instance.'''

        try:
            self.client.start_instances(
                InstanceIds=[instance_id],
                DryRun=False
            )
        except ClientError as e:
            logging.error(
                '인스턴스 시작 API (`start_instances()`) 호출 실패 | 인스턴스 ID: %s | %s',
                instance_id,
                e
            )

    def stop_instance(self, instance_id: str) -> None:
        '''Stop the EC2 instance.'''

        try:
            self.client.stop_instances(
                InstanceIds=[instance_id],
                DryRun=False
            )
        except ClientError as e:
            logging.error(
                '인스턴스 중지 API (`stop_instances()`) 호출 실패 | 인스턴스 ID: %s | %s',
                instance_id,
                e
            )

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
            instance_id = reservation['Instances'][0]['InstanceId']
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

    def get_runinstance_events(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        ''' 지정된 시간 범위에 생성된 Runinstances 로그들을 추출합니다.'''

        runinstance_events = []
        response = self.client.lookup_events(
            LookupAttributes=[
                {'AttributeKey': 'EventName', 'AttributeValue': 'RunInstances'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=50,
        )
        runinstance_events.extend(response['Events'])

        while 'NextToken' in response:
            response = self.client.lookup_events(
                LookupAttributes=[
                    {'AttributeKey': 'EventName', 'AttributeValue': 'RunInstances'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                MaxResults=50,
                NextToken=response['NextToken']
            )
            runinstance_events.extend(response['Events'])

        return runinstance_events

    def get_event_logs_by_event_names(
        self,
        event_name: str = "StartInstances",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Optional[list[dict]]:
        ''' 지정된 시간 범위에 생성된 CloudTrail 로그들을 중 해당 event name에 알맞는 log들을 추출합니다.

        Args:
            event_names (list[str]) : AWS CloudTrail Event history의 Event name 입니다. 
            start_time (datetime) : 조회 시작 시간으로 UTC 기준 시간이 들어와야 합니다. 
            end_time (datetime) : 조회 종료 시간으로 UTC 기준 시간이 들어와야 합니다.  
        '''

        event_logs = []

        if (start_time is None or not isinstance(start_time, datetime)):
            raise TypeError('start time은 datetime 이여야 합니다.')
        elif (end_time is None or not isinstance(end_time, datetime)):
            raise TypeError('end time은 datetime 이여야 합니다.')

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

        event_logs.extend(response['Events'])

        while 'NextToken' in response:
            response = self.client.lookup_events(
                LookupAttributes=[
                    {'AttributeKey': 'EventName', 'AttributeValue': event_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                MaxResults=50,
                NextToken=response['NextToken']
            )
            event_logs.extend(response['Events'])

        return event_logs

    def get_instance_owner_info(
        self,
        runinstance_events: list[dict]
    ) -> list[tuple[str, str]]:
        '''Log들 중 instance id와 instance의 소유권 정보를 추출'''

        owner_info_list = []

        for event in runinstance_events:
            user_name = event['Username']
            for resource in event['Resources']:
                if resource['ResourceType'] == 'AWS::EC2::Instance':
                    instance_id = resource['ResourceName']
                    break

            owner_info_list.append((user_name, instance_id))

        return owner_info_list
