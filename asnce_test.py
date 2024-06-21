# import asyncio


# async def delayed_task():
#     # 30분(1800초) 대기
#     await asyncio.sleep(10)
#     # 30분 후에 실행할 작업
#     print("10 후에 실행될 작업")

# # asyncio 이벤트 루프 생성 및 delayed_task 실행
# loop = asyncio.get_event_loop()
# loop.run_until_complete(delayed_task())
# loop.close()

import threading


def delayed_task():
    # 30분 후에 실행할 작업
    print("10초 후에 실행될 작업")


# 30분(1800초) 후에 delayed_task 함수 실행
timer = threading.Timer(10, delayed_task)
timer.start()
