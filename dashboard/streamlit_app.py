from __future__ import annotations

import os
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import httpx
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


st.set_page_config(page_title="AllStar AI + VOC", page_icon="⭐", layout="wide")
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
        f"생성 {generation['provider']} / {generation['model']} / {generation['reasoning']}\n"
        f"평가 {judge['provider']} / {judge['model']} / {judge['reasoning']}"
    )


st.title("⭐ AllStar 통합 AI 품질 포트폴리오")
st.caption("AI Agent와 VOC 멀티 에이전트를 한 화면에서 실행하고 품질 결과를 확인합니다.")

tab_ai, tab_voc, tab_reports, tab_monitoring = st.tabs(
    ["AI Agent 챗봇", "VOC 챗봇", "통합 리포트", "통합 모니터링"]
)

with tab_ai:
    st.subheader("AI Agent 챗봇")
    st.caption("기존 포트폴리오 API(:8000)를 사용합니다.")
    for message in st.session_state.setdefault("ai_history", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])
    if question := st.chat_input("AI Agent에게 질문하세요", key="ai_question"):
        st.session_state.ai_history.append({"role": "user", "content": question})
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                response = client.post(f"{PORTFOLIO_API}/chat", json={"question": question})
                response.raise_for_status()
                body = response.json()
            answer = body.get("answer", "응답이 없습니다.")
        except Exception as error:
            answer = f"AI Agent API 연결 실패: {error}"
        st.session_state.ai_history.append({"role": "assistant", "content": answer})
        st.rerun()

with tab_voc:
    st.subheader("VOC 단발 질문 챗봇")
    st.info("A~D는 답변 생성 모델과 독립 품질 평가 모델의 조합입니다. 선택은 현재 질문 1건에만 적용됩니다.")
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
                    f"<div class='profile-model'>답변 생성: {generation['provider']} / {generation['model']} / {generation['reasoning']}<br>"
                    f"품질 평가: {judge['provider']} / {judge['model']} / {judge['reasoning']}</div></div>",
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
        st.warning("VOC API에 연결할 수 없습니다. Server Control Center에서 VOC 서비스를 시작하세요.")

    st.markdown(f"현재 선택: **{st.session_state.voc_profile}**")
    for message in st.session_state.setdefault("voc_history", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("meta"):
                st.caption(message["meta"])

    if pending:
        status = get_json(f"{VOC_API}/chat/{pending}/status")
        if status:
            stages = ["① 의도 분석", "② VOC 검색", "③ 요약", "④ 평가", "⑤ 비판", "⑥ 최종 개선", "⑦ LLM Judge"]
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
                        f"Judge {judge_result.get('total', 'N/A')} / {judge_result.get('verdict', 'N/A')}"
                    )
                else:
                    answer = f"처리 실패: {status.get('error', '원인 없음')}"
                    meta = f"프로필 {status['profile_id']} · 실패"
                st.session_state.voc_history.append({"role": "assistant", "content": answer, "meta": meta})
                st.session_state.voc_pending = None
                st.rerun()
            time.sleep(1)
            st.rerun()

    if question := st.chat_input("VOC 관련 단발 질문을 입력하세요", key="voc_question", disabled=bool(pending)):
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
            st.session_state.voc_history.append({"role": "assistant", "content": f"VOC 요청 실패: {error}"})
        st.rerun()

with tab_reports:
    st.subheader("통합 리포트")
    if st.button("VOC 실시간 리포트 생성"):
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
    st.subheader("통합 모니터링")
    st.link_button("Grafana 열기", GRAFANA)
    st.link_button("Prometheus 열기", "http://localhost:9090")
    st.link_button("Portfolio Swagger", f"{PORTFOLIO_API}/docs")
    st.link_button("VOC Swagger", f"{VOC_API}/docs")
