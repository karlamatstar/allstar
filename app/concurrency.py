import threading

# 한 번에 OpenAI로 나가는 동시 호출 수 상한 (에이전트 답변 생성 + 저지 채점 공용).
# 계정 요금제의 분당 요청 한도(RPM)에 맞춰 조정한다.
OPENAI_CONCURRENCY_LIMIT = 5
openai_call_semaphore = threading.Semaphore(OPENAI_CONCURRENCY_LIMIT)

# 재시도 사이 대기시간(초). attempt번째 실패 후 BACKOFF_BASE_SECONDS * 2**(attempt-1)만큼 대기한다.
BACKOFF_BASE_SECONDS = 1.0
