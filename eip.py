import os

import boto3
# from botocore.exceptions import ClientError


ec2 = boto3.client(
    'ec2',
    aws_access_key_id=os.getenv('INSTANCE_MANAGER_AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('INSTANCE_MANAGER_AWS_SECRET_ACCESS_KEY'),
)


def get_instance_id_list(ec2):
    instance_id_list = []
    response = ec2.describe_instances(Filters=[
        {
            'Name': 'instance-state-name',
            'Values': [
                'running',
                'stopped',
            ],
        },
    ])

    reservations = response['Reservations']
    for reservation in reservations:
        instance = reservation['Instances'][0]
        instance_id = instance['InstanceId']
        instance_id_list.append(instance_id)

    return instance_id_list


def associate_eip_to_instance(ec2):
    instance_id_list = get_instance_id_list(ec2)
    # instance_id_list = ['i-0232e8642341bcbe0']

    for instance_id in instance_id_list:
        try:
            allocation = ec2.allocate_address(
                TagSpecifications=[
                    {
                        'ResourceType': "elastic-ip",
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': f'EIP for {instance_id}',
                            },
                        ],
                    },
                ]
            )
            ec2.associate_address(
                AllocationId=allocation['AllocationId'],
                InstanceId=instance_id,
            )
        except Exception as e:
            print(f'Error: {e}')  # TODO: Logging, Exception handling
            print(f'Instance ID: {instance_id}')


if __name__ == '__main__':
    associate_eip_to_instance(ec2)
