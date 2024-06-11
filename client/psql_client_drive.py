from psql_client import PSQLClient


if __name__ == '__main__':
    psql_client = PSQLClient()
    student_id = '2'
    ret = psql_client.get_latest_started_instance_id(student_id)
    ret
