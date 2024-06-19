'''iam user 정보가 포함된 csv의 data를 DB에 적재하는 기능 구현.'''


import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(app_dir)

if __name__ == '__main__':
    import pandas as pd

    from client.psql_client import PSQLClient

    # csv에 따라 변경되여야 합니다.
    CSV_FILE_PATH = './student_AWS_IAM_Username.csv'
    IAM_COL_NAME_IN_CSV = 'IAM 사용자 이름'
    STUDNET_NAME_IN_CSV = '교육생'

    psql_client = PSQLClient()

    csv_df = pd.read_csv(CSV_FILE_PATH)
    student_info = psql_client.get_student_info()
    psql_df = pd.DataFrame(student_info, columns=['student_id', 'name'])
    data_to_db = []

    combined_df = pd.merge(csv_df, psql_df, left_on=STUDNET_NAME_IN_CSV,
                           right_on='name', how='inner')
    combined_df = combined_df[[IAM_COL_NAME_IN_CSV, 'student_id']]

    for tuple_row in combined_df.to_numpy():
        data_to_db.append(tuple(tuple_row))

    psql_client.insert_into_iam_user(data_to_db)
