from __future__ import annotations

import streamlit as st

from allstar.ui.dashboard.views import (
    render_ai_chat,
    render_ai_testcases,
    render_monitoring,
    render_reports,
    render_voc_chat,
    render_voc_testcases,
    watch_voc_report_updates,
)


st.set_page_config(page_title="AI Agent QA AllStar", page_icon="⭐", layout="wide")

st.markdown(
    """
<style>
:root {
    --allstar-card:#ffffff;
    --allstar-border:#d8e0ec;
    --allstar-text:#172033;
    --allstar-muted:#64748b;
    --allstar-selected:#304f7d;
}
@media (prefers-color-scheme: dark) {
    :root {
        --allstar-card:#171f2e;
        --allstar-border:#334155;
        --allstar-text:#e5e9f0;
        --allstar-muted:#94a3b8;
        --allstar-selected:#6f96cc;
    }
}
.block-container {max-width:1760px; padding-top:1rem; padding-bottom:2rem;}
header[data-testid="stHeader"] {height:0; visibility:hidden;}
#MainMenu, footer {visibility:hidden;}

/* 선택 여부에 따라 탭 크기가 변하지 않게 하고, 다섯 번째 상위 탭부터 오른쪽 QA 영역으로 분리한다. */
[data-baseweb="tab-list"] [data-baseweb="tab"] {
    box-sizing:border-box; min-height:3.25rem; padding:.65rem .9rem !important;
    font-weight:750; white-space:normal; text-align:center; line-height:1.2;
}
[data-baseweb="tab-list"] [aria-selected="true"] {color:var(--allstar-selected) !important;}
[data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
  [data-baseweb="tab"]:nth-child(5),
[data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
  button[role="tab"]:nth-child(5) {
    margin-left:auto !important;
    padding-left:2rem !important;
    border-left:1px solid var(--allstar-border) !important;
}

.allstar-banner {
    padding:1rem 1.35rem; margin-bottom:.8rem; border-radius:14px; color:#fff;
    background:linear-gradient(120deg,#111c3a 0%,#1e335f 58%,#365f91 100%);
    box-shadow:0 8px 24px rgba(17,28,58,.22);
}
.allstar-banner h1 {font-size:1.65rem; margin:0 0 .2rem; color:#fff;}
.allstar-banner p {margin:0; color:rgba(255,255,255,.9); font-weight:600;}
.profile-card {
    box-sizing:border-box; height:16rem; overflow-y:auto; border:1px solid var(--allstar-border);
    border-radius:14px; padding:12px; background:var(--allstar-card); display:flex; flex-direction:column;
}
.profile-card.profile-running {
    border:2px solid #2f80ed; background:linear-gradient(145deg, rgba(47,128,237,.22), var(--allstar-card));
    box-shadow:0 0 0 3px rgba(47,128,237,.12), 0 8px 22px rgba(47,128,237,.14);
}
.profile-card.profile-completed {
    border:2px solid #d97706; background:linear-gradient(145deg, rgba(217,119,6,.20), var(--allstar-card));
    box-shadow:0 0 0 3px rgba(217,119,6,.10);
}
.profile-status {display:inline-block; margin-bottom:.5rem; padding:.18rem .55rem; border-radius:999px; font-size:.78rem; font-weight:800;}
.profile-running .profile-status {background:#2f80ed; color:#fff;}
.profile-completed .profile-status {background:#d97706; color:#fff;}
.profile-title {font-size:1.08rem; font-weight:800; margin-bottom:6px; min-height:2.8rem;}
.profile-summary {min-height:4.2rem; color:var(--allstar-muted);}
.profile-card hr {width:100%; margin:10px 0; border-color:var(--allstar-border);}
.profile-model {font-size:.85rem; color:var(--allstar-muted); line-height:1.45; margin-top:auto;}
.scope-box {border:1px solid var(--allstar-border); border-radius:12px; padding:.8rem 1rem; background:var(--allstar-card);}
.required-confirm-title {color:#b45309; font-size:.82rem; font-weight:900; letter-spacing:.02em; margin-bottom:.2rem;}
[class*="st-key-required_api_confirm_"] {
    box-sizing:border-box; border:1px solid #e59b24; border-radius:12px;
    background:linear-gradient(135deg, rgba(245,158,11,.17), rgba(245,158,11,.07));
    padding:.7rem 1rem .55rem; margin:.7rem 0 .9rem;
    box-shadow:0 0 0 2px rgba(245,158,11,.06);
}
[class*="st-key-required_api_confirm_"] [data-testid="stCheckbox"] label p {font-weight:750; color:var(--allstar-text);}
.stage-detail {border:1px solid var(--allstar-border); border-radius:12px; padding:1rem; background:var(--allstar-card);}
.stage-flow {display:flex; align-items:stretch; gap:.38rem; width:max-content; min-width:max-content; margin:.8rem 0 .45rem; overflow:visible; padding:.2rem 0;}
.stage-node {flex:0 0 180px; width:180px; min-height:112px; border:1px solid var(--allstar-border); border-radius:12px; padding:.65rem .55rem; background:var(--allstar-card); text-align:center; display:flex; flex-direction:column; justify-content:center;}
.stage-node span {font-size:.76rem; font-weight:800; opacity:.8;}
.stage-node b {font-size:.91rem; margin:.15rem 0;}
.stage-node small {font-size:.72rem; color:var(--allstar-muted);}
.stage-node em {font-size:.76rem; font-style:normal; font-weight:800; margin-top:.35rem;}
.stage-running {border:2px solid #2f80ed; background:rgba(47,128,237,.18); box-shadow:0 0 0 3px rgba(47,128,237,.10);}
.stage-running em {color:#2f80ed;}
.stage-done {border-color:#188a4c; background:rgba(24,138,76,.13);}
.stage-done em {color:#188a4c;}
.stage-failed {border-color:#c0392b; background:rgba(192,57,43,.13);}
.stage-failed em {color:#c0392b;}
.stage-skipped {border-style:dashed; opacity:.72;}
.stage-arrow {flex:0 0 26px; width:26px; align-self:center; color:var(--allstar-muted); font-size:1.3rem; font-weight:900; text-align:center;}
.stage-button-arrow {display:flex; width:26px; height:4.5rem; align-items:center; justify-content:center; color:var(--allstar-muted); font-size:1.25rem; font-weight:900;}
[class*="st-key-stage_scroll_"] {overflow-x:auto; overflow-y:hidden; padding-bottom:.55rem;}
[class*="st-key-stage_scroll_"] > div {min-width:max-content;}
[class*="st-key-stage_buttons_"] [data-testid="stHorizontalBlock"] {flex-wrap:nowrap !important; gap:.38rem !important; min-width:max-content;}
[class*="st-key-stage_cell_"] {flex:0 0 180px !important; width:180px !important; min-width:180px !important; max-width:180px !important;}
[class*="st-key-stage_cell_"] > div {width:180px !important; min-width:180px !important;}
[class*="st-key-stage_buttons_"] [data-testid="stButton"] {width:180px !important; min-width:180px !important;}
[class*="st-key-stage_buttons_"] [data-testid="stButton"] button {
    width:180px !important; min-width:180px !important; height:4.5rem !important; padding:.55rem .45rem !important;
}
[class*="st-key-stage_buttons_"] [data-testid="stButton"] button p {
    width:100% !important; white-space:pre-line !important; word-break:keep-all !important;
    overflow-wrap:normal !important; hyphens:none !important; line-height:1.35 !important;
}
[class*="st-key-stage_arrow_"] {flex:0 0 26px !important; width:26px !important; min-width:26px !important; max-width:26px !important;}
[class*="st-key-stage_arrow_"] > div {width:26px !important; min-width:26px !important;}
/* 부분 갱신 중 기존 화면 전체가 회색으로 흐려지는 Streamlit stale 효과를 제거한다. */
[data-stale="true"] {opacity:1 !important;}
@media (max-width:1200px) {
    .profile-card {height:19rem;}
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      [data-baseweb="tab"]:nth-child(5),
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      button[role="tab"]:nth-child(5) {margin-left:1rem !important; padding-left:1rem !important;}
}
@media (max-width:900px) {
    .profile-card {height:auto; min-height:0; overflow-y:visible; padding:10px 12px;}
    .profile-title, .profile-summary {min-height:0;}
    .profile-summary {margin-bottom:.55rem;}
    .profile-model {margin-top:.25rem;}
    [data-baseweb="tab-list"] {overflow-x:auto; flex-wrap:nowrap;}
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      [data-baseweb="tab"]:nth-child(5),
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      button[role="tab"]:nth-child(5) {margin-left:0 !important; padding-left:.9rem !important; border-left:0 !important;}
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="allstar-banner">
  <h1>⭐ AI Agent QA AllStar</h1>
  <p>AI 에이전트와 고객 의견 분석(VOC)의 대화·품질검사·모니터링·보고서를 한 화면에서 관리합니다.</p>
</div>
""",
    unsafe_allow_html=True,
)

watch_voc_report_updates()

(
    tab_ai_chat,
    tab_voc_chat,
    tab_monitoring,
    tab_reports,
    tab_ai_cases,
    tab_voc_cases,
) = st.tabs(
    [
        "AI 에이전트 챗봇\n(AI Agent)",
        "VOC 챗봇\n(VOC)",
        "모니터링\n(Monitoring)",
        "리포트 모음\n(Reports)",
        "AI 에이전트 테스트케이스\n(AI Agent QA)",
        "VOC 테스트케이스\n(VOC QA)",
    ]
)

with tab_ai_chat:
    render_ai_chat()

with tab_voc_chat:
    render_voc_chat()

with tab_monitoring:
    render_monitoring()

with tab_reports:
    render_reports()

with tab_ai_cases:
    render_ai_testcases()

with tab_voc_cases:
    render_voc_testcases()
