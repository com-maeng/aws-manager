'''인스턴스 사용량을 관리하는 모듈'''


from datetime import datetime, timedelta

import holidays
from pytz import timezone


class InstanceUsageManager:
    '''인스턴스의 사용량을 관리하고 일별 사용 한도와 공휴일을 고려하여 사용량을 추적하는 클래스.'''

    def __init__(self) -> None:
        self.today_date = datetime.now(timezone('Asia/Seoul'))
        self.midnight_time = datetime.combine(
            self.today_date,
            datetime.min.time()
        ).astimezone(timezone('Asia/Seoul'))
        self.throshold_time = self.get_threshold_time()

    def get_threshold_time(self) -> timedelta:
        '''공휴일과 주말을 기준으로 인스턴스의 일별 할당 시간을 계산.'''

        year = self.today_date.year
        kr_holidays = holidays.country_holidays('KR', years=year)

        if self.today_date in kr_holidays or self.today_date.weekday() >= 5:
            threshold_time = 12
        else:
            threshold_time = 6

        return timedelta(hours=threshold_time)

    def get_remaining_time(self, logs: list[tuple[str, str]]) -> timedelta:
        '''오늘의 Log들을 통해 총 instance 사용 시간 계산 후 남은 사용 시간을 반환합니다. '''

        total_usage_time = timedelta()

        for idx, log in enumerate(logs[::2]):
            start_time = log[-1]

            try:
                stop_time = logs[idx*2 + 1][-1]
                usage_time = stop_time - start_time
            except IndexError:
                usage_time = datetime.now() - start_time

            total_usage_time += usage_time

        return self.throshold_time - total_usage_time
