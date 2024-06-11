import logging

from aws_client import EC2Client


# Set up a root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

if __name__ == "__main__":
    ec2_client = EC2Client()
    print(ec2_client.get_instance_state('i-0f88debd1716520ec'))
