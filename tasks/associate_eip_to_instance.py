'''EIP 주소를 생성하여 시작/중지 상태인 모든 EC2 인스턴스에 하나씩 할당합니다.'''


import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(app_dir)


if __name__ == '__main__':
    from client.aws_client import EC2Client

    ec2_client = EC2Client()
    instance_id_list = ec2_client.get_live_instance_id_list(
        ['running', 'stopped'])
    allocation_id_list = ec2_client.allocate_eip_address(
        len(instance_id_list)
    )

    ec2_client.associate_eip_address(instance_id_list, allocation_id_list)
