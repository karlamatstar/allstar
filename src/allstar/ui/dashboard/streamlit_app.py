from __future__ import annotations

import os
import time

import httpx
import streamlit as st



st.set_page_config(page_title="AllStar 통합 상담·고객 의견 분석", page_icon="⭐", layout="wide")
PORTFOLIO_API = os.getenv("PORTFOLIO_API_URL", "http://localhost:8000")
VOC_API = os.getenv("VOC_API_URL", "http://localhost:8100")
GRAFANA = os.getenv("GRAFANA_URL", "http://localhost:3000")
TIMEOUT = httpx.Timeout(190.0, connect=5.0)

st.markdown("""
<style>
.block-container {max-width: 1500px; padding-top: 1.2rem;}
.profile-card {border:1px solid #d8dee9;border-radius:14px;padding:12px;min-height:154px;background:#fff;}
.profile-title {font-size:1.08rem;font-weight:800;margin-bottom:6px;}
.profile-model {font-size:.85rem;color:#425466;line-height:1.45;}
.stage {border:1px solid #d8dee9;border-radius:10px;padding:8px;text-align:center;font-size:.82rem;min-height:68px;}
</style>
""", unsafe_allow_html=True)


def get_json(url: str) -> dict | list | None:
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception:
        return None


def profile_text(profile: dict) -> str:
    generation = profile["generation"]
    judge = profile["judge"]
    return (
        f"{profile['profile_id']} · {profile['title']}\n"
        f"답변 생성 {generation['provider']} / {generation['model']} / {reasoning_text(generation['reasoning'])}\n"
        f"독립 품질 평가(Judge) {judge['provider']} / {judge['model']} / {reasoning_text(judge['reasoning'])}"
    )


def reasoning_text(value: str) -> str:
    labels = {
        "none": "추론 끔(none)",
        "low": "낮음(low)",
        "medium": "중간(medium)",
        "high": "높음(high)",
    }
    return labels.get(value, value)


st.title("⭐ AllStar 통합 AI 품질 포트폴리오")
st.caption("AI 상담 에이전트(AI Agent)와 고객 의견 분석(VOC)을 한 화면에서 실행하고 품질 결과를 확인합니다.")

tab_ai, tab_voc, tab_reports, tab_monitoring = st.tabs(
    ["AI 상담 챗봇 (AI Agent)", "고객 의견 분석 (VOC)", "통합 결과 보고서 (Report)", "통합 상태 확인 (Monitoring)"]
)

with tab_ai:
    st.subheader("AI 상담 챗봇 (AI Agent)")
    st.caption("AI 상담 서버와 연결되는 프로그램 통로(API, :8000)를 사용합니다.")
    for message in st.session_state.setdefault("ai_history", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])
    if question := st.chat_input("AI 상담 에이전트에게 질문하세요", key="ai_question"):
        st.session_state.ai_history.append({"role": "user", "content": question})
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                response = client.post(f"{PORTFOLIO_API}/chat", json={"question": question})
                response.raise_for_status()
                body = response.json()
            answer = body.get("answer", "응답이 없습니다.")
        except Exception as error:
            answer = f"AI 상담 서버(API) 연결 실패: {error}"
        st.session_state.ai_history.append({"role": "assistant", "content": answer})
        st.rerun()

with tab_voc:
    st.subheader("고객 의견 분석(VOC) 단발 질문")
    st.info("A~D는 답변 생성 모델과 독립 품질 평가 모델(Judge)의 조합입니다. 선택은 현재 질문 1건에만 적용됩니다.")
    profiles = get_json(f"{VOC_API}/profiles") or []
    pending = st.session_state.get("voc_pending")
    selected = st.session_state.setdefault("voc_profile", "A")

    if profiles:
        columns = st.columns(4)
        for column, profile in zip(columns, profiles):
            generation = profile["generation"]
            judge = profile["judge"]
            with column:
                st.markdown(
                    f"<div class='profile-card'><div class='profile-title'>"
                    f"{profile['profile_id']} · {profile['title']}</div>"
                    f"<div>{profile['summary']}</div><hr>"
                    f"<div class='profile-model'>답변 생성: {generation['provider']} / {generation['model']} / 추론 강도 {reasoning_text(generation['reasoning'])}<br>"
                    f"독립 품질 평가(Judge): {judge['provider']} / {judge['model']} / 추론 강도 {reasoning_text(judge['reasoning'])}</div></div>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "✓ 선택됨" if selected == profile["profile_id"] else "선택",
                    key=f"profile_{profile['profile_id']}",
                    disabled=bool(pending) or not profile.get("available", True),
                    use_container_width=True,
                ):
                    st.session_state.voc_profile = profile["profile_id"]
                    st.rerun()
                if not profile.get("available", True):
                    st.caption("필수 키 설정 필요: " + ", ".join(profile.get("missing_keys", [])))
    else:
        st.warning("고객 의견 분석 서버(VOC API)에 연결할 수 없습니다. 'AllStar 서버 관리'에서 해당 서비스를 시작하세요.")

    st.markdown(f"현재 선택: **{st.session_state.voc_profile}**")
    for message in st.session_state.setdefault("voc_history", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("meta"):
                st.caption(message["meta"])

    if pending:
        status = get_json(f"{VOC_API}/chat/{pending}/status")
        if status:
            stages = [
                "① 질문 의도 분석 (Interpreter)",
                "② 관련 의견 검색 (Retriever)",
                "③ 내용 요약 (Summarizer)",
                "④ 초기 품질 평가 (Evaluator)",
                "⑤ 결과 검토 (Critic)",
                "⑥ 최종 답변 개선 (Improver)",
                "⑦ 독립 품질 평가 (LLM Judge)",
            ]
            cols = st.columns(7)
            terminal = status["status"] in {"completed", "failed"}
            for col, name in zip(cols, stages):
                col.markdown(
                    f"<div class='stage'>{'✓ 완료' if terminal and status['status']=='completed' else '◔ 처리 중'}<br>{name}</div>",
                    unsafe_allow_html=True,
                )
            st.progress(100 if terminal else min(95, int(status["elapsed_seconds"] % 95) + 1))
            st.caption(f"{status['current_stage']} · {status['elapsed_seconds']:.1f}초 경과 · 프로필 {status['profile_id']}")
            if terminal:
                if status["status"] == "completed":
                    result = status.get("result") or {}
                    answer = result.get("answer") or result.get("policy") or result.get("summary") or "결과 없음"
                    judge_result = status.get("judge") or {}
                    meta = (
                        f"프로필 {status['profile_id']} · {status['elapsed_seconds']:.1f}초 · "
                        f"독립 평가(Judge) {judge_result.get('total', 'N/A')} / 판정 {judge_result.get('verdict', 'N/A')}"
                    )
                else:
                    answer = f"처리 실패: {status.get('error', '원인 없음')}"
                    meta = f"프로필 {status['profile_id']} · 실패"
                st.session_state.voc_history.append({"role": "assistant", "content": answer, "meta": meta})
                st.session_state.voc_pending = None
                st.rerun()
            time.sleep(1)
            st.rerun()

    if question := st.chat_input("고객 의견(VOC) 관련 단발 질문을 입력하세요", key="voc_question", disabled=bool(pending)):
        st.session_state.voc_history.append({"role": "user", "content": question})
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{VOC_API}/chat",
                    json={"question": question, "profile_id": st.session_state.voc_profile},
                )
                response.raise_for_status()
                st.session_state.voc_pending = response.json()["request_id"]
        except Exception as error:
            st.session_state.voc_history.append({"role": "assistant", "content": f"고객 의견 분석(VOC) 요청 실패: {error}"})
        st.rerun()

with tab_reports:
    st.subheader("통합 결과 보고서 (Report)")
    if st.button("고객 의견 분석(VOC) 실시간 보고서 생성"):
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(f"{VOC_API}/reports/live/generate")
                response.raise_for_status()
            st.success("리포트를 생성했습니다.")
            st.json(response.json())
        except Exception as error:
            st.error(f"리포트 생성 실패: {error}")
    st.caption("실시간 챗봇 로그와 테스트케이스·교차검증 리포트는 서로 분리해 저장됩니다.")

with tab_monitoring:
    st.subheader("통합 상태 확인 (Monitoring)")
    st.caption("운영 그래프, 상태 수집 정보, 서버 기능 명세를 각각 확인할 수 있습니다.")
    st.link_button("운영 상태 화면 열기 (Grafana)", GRAFANA)
    st.link_button("상태 정보 수집 화면 열기 (Prometheus)", "http://localhost:9090")
    st.link_button("AI 상담 서버 기능 명세 열기 (Portfolio Swagger)", f"{PORTFOLIO_API}/docs")
    st.link_button("고객 의견 분석 서버 기능 명세 열기 (VOC Swagger)", f"{VOC_API}/docs")
