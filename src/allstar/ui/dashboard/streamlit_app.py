from __future__ import annotations

import streamlit as st

from allstar.ui.dashboard.views import (
    render_ai_chat,
    render_ai_testcases,
    render_monitoring,
    render_reports,
    render_voc_chat,
    render_voc_testcases,
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
.profile-title {font-size:1.08rem; font-weight:800; margin-bottom:6px; min-height:2.8rem;}
.profile-summary {min-height:4.2rem; color:var(--allstar-muted);}
.profile-card hr {width:100%; margin:10px 0; border-color:var(--allstar-border);}
.profile-model {font-size:.85rem; color:var(--allstar-muted); line-height:1.45; margin-top:auto;}
.scope-box {border:1px solid var(--allstar-border); border-radius:12px; padding:.8rem 1rem; background:var(--allstar-card);}
.stage-detail {border:1px solid var(--allstar-border); border-radius:12px; padding:1rem; background:var(--allstar-card);}
@media (max-width:1200px) {
    .profile-card {height:19rem;}
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      [data-baseweb="tab"]:nth-child(5),
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      button[role="tab"]:nth-child(5) {margin-left:1rem !important; padding-left:1rem !important;}
}
@media (max-width:900px) {
    .profile-card {height:22rem;}
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
