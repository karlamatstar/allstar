import json
import sys
import time
import urllib.error
import urllib.request

# 서버 컴퓨터에 test_cases.json이 없는 배포용 exe 환경에서도 쓸 수 있도록 기본 질문을 하드코딩해둔다
# (서버 컴퓨터에서 직접 실행할 때는 __main__에서 실제 ai_quality/test_cases.json의 첫 케이스로 대체된다).
DEFAULT_QUESTION = "이 교육과정은 총 몇 시간인가요?"


def run_api_disconnect_test(target_host: str, question: str = DEFAULT_QUESTION, on_line=None) -> dict:
    """의도적인 API 장애(503)를 유발해 챗봇의 Graceful Fallback을 검증한다.
    target_host: "IP:포트" 형식 (예: "192.168.0.22:8000"). 결과 요약 dict를 반환한다."""
    def emit(text):
        if on_line:
            on_line(text)
        else:
            print(text, end='', flush=True)

    emit("🚀 API 끊김 방어 테스트 시작...\n")
    emit(f"\n[선택된 질문]: {question}\n")
    emit("의도적인 API 장애(503)를 유발하여 챗봇의 Graceful Fallback 파이프라인을 검증합니다.\n")
    emit("-" * 60 + "\n\n")

    payload = json.dumps({
        "question": question,
        "is_latency_test": False,
        "simulate_api_disconnect": True,
    }).encode("utf-8")

    url = f"http://{target_host}/chat"
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )

    result = {"ok": False, "latency": None, "answer": None, "error": None}
    try:
        start = time.time()
        emit("서버에 요청 전송 중... (API 연결 실패 시 3회 재시도를 거치므로 최대 15초 이상 소요될 수 있습니다.)\n")
        with urllib.request.urlopen(request, timeout=60) as response:
            latency = time.time() - start
            data = json.loads(response.read().decode("utf-8"))
            result.update(ok=True, latency=latency, answer=data.get("answer"))
            emit(f"\n✅ 응답 수신 성공! (응답시간: {latency:.1f}초)\n")
            emit(f"A: {data.get('answer')}\n")
            emit("\n💡 테스트 결과: 챗봇 서버가 뻗지 않고(HTTP 200) 사용자에게 친절한 에러 안내(Fallback)를 정상 반환했습니다.\n")
            emit("이제 백그라운드 AI 채점관이 위 답변을 'FAIL'로 채점하여 Jira에 장애 버그 티켓을 자동 등록하게 됩니다.\n")
    except urllib.error.HTTPError as error:
        result["error"] = f"HTTP {error.code}"
        emit(f"\n❌ 예기치 않은 서버 에러 발생! HTTP {error.code}\n")
        emit(error.read().decode("utf-8", errors="replace") + "\n")
    except Exception as error:
        result["error"] = str(error)
        emit(f"\n❌ 요청 중 오류 발생: {error}\n")
    return result


if __name__ == "__main__":
    import os

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # 서버(개발자) 컴퓨터에서 프로젝트 전체를 두고 직접 실행할 때는 실제 큐레이션된 첫 테스트 케이스를 사용
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "ai_quality", "test_cases.json")
    question = DEFAULT_QUESTION
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        question = data[0]["user_question"]
    except (OSError, json.JSONDecodeError, KeyError, IndexError):
        pass

    run_api_disconnect_test("127.0.0.1:8000", question=question)
