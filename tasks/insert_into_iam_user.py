'''iam user 정보가 포함된 csv의 data를 DB에 적재하는 기능 구현.'''


import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(app_dir)

if __name__ == '__main__':
    import csv

    from client.psql_client import PSQLClient

    # csv에 따라 변경되어야 합니다.
    CSV_FILE_PATH = './student_AWS_IAM_Username.csv'

    psql_client = PSQLClient()
    student_info = psql_client.get_name_and_student_id()
    student_info_dict = dict(student_info)

    data_to_db = []

    with open(CSV_FILE_PATH, mode='r', newline='', encoding='utf-8') as file:
        csv_data = csv.reader(file)

        for row in csv_data:
            name = row[1]  # csv에 기재된 한글 본명 정보
            iam_user = row[2]

            if student_info_dict.get(name):
                student_id = student_info_dict[name]
                data_to_db.append((iam_user, student_id))

    psql_client.insert_into_iam_user(data_to_db)
