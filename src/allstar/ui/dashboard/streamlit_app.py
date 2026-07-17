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
    color-scheme:light;
    --allstar-bg:#f4f7fb;
    --allstar-surface:#ffffff;
    --allstar-surface-soft:#edf3fa;
    --allstar-card:#ffffff;
    --allstar-border:#d8e0ec;
    --allstar-text:#172033;
    --allstar-muted:#64748b;
    --allstar-selected:#245fa6;
    --allstar-selected-text:#ffffff;
    --allstar-input:#ffffff;
    --allstar-shadow:0 6px 18px rgba(30,51,95,.08);
}
@media (prefers-color-scheme: dark) {
    :root {
        color-scheme:dark;
        --allstar-bg:#0d1420;
        --allstar-surface:#151e2d;
        --allstar-surface-soft:#1b2738;
        --allstar-card:#172233;
        --allstar-border:#36465d;
        --allstar-text:#edf2f8;
        --allstar-muted:#a8b5c7;
        --allstar-selected:#4f8fd8;
        --allstar-selected-text:#ffffff;
        --allstar-input:#111a28;
        --allstar-shadow:0 8px 22px rgba(0,0,0,.30);
    }
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background:var(--allstar-bg) !important; color:var(--allstar-text) !important;
}
.block-container {max-width:1760px; padding-top:1rem; padding-bottom:2rem;}
header[data-testid="stHeader"] {height:0; visibility:hidden;}
#MainMenu, footer {visibility:hidden;}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp p, .stApp label, .stApp [data-testid="stCaptionContainer"] {
    color:var(--allstar-text);
}
.stApp [data-testid="stCaptionContainer"], .stApp small {color:var(--allstar-muted) !important;}
.stApp [data-testid="stExpander"],
.stApp [data-testid="stVerticalBlockBorderWrapper"] {
    border-color:var(--allstar-border) !important; background:var(--allstar-surface) !important;
}
.stApp [data-baseweb="select"] > div,
.stApp [data-baseweb="input"] > div,
.stApp [data-baseweb="textarea"] > div,
.stApp [data-testid="stTextInputRootElement"],
.stApp [data-testid="stTextAreaRootElement"] {
    background:var(--allstar-input) !important; border-color:var(--allstar-border) !important;
    color:var(--allstar-text) !important;
}
.stApp input, .stApp textarea {color:var(--allstar-text) !important;}
.stApp [data-testid="stDataFrame"], .stApp [data-testid="stTable"] {
    border-radius:10px; border:1px solid var(--allstar-border); background:var(--allstar-surface);
}

/* 탭을 독립된 버튼처럼 구분하되 선택 여부에 따라 크기가 변하지 않게 한다. */
[data-baseweb="tab-list"], [role="tablist"] {
    box-sizing:border-box; gap:.38rem !important; padding:.35rem !important;
    border:1px solid var(--allstar-border); border-radius:12px;
    background:var(--allstar-surface-soft); box-shadow:var(--allstar-shadow);
    overflow-x:auto; overflow-y:hidden; scrollbar-width:thin;
}
[data-baseweb="tab-list"] [data-baseweb="tab"], [role="tablist"] [data-testid="stTab"] {
    box-sizing:border-box; flex:0 0 auto; min-height:3.25rem; min-width:7.2rem;
    padding:.65rem .9rem !important; border:1px solid transparent !important; border-radius:9px !important;
    background:var(--allstar-surface) !important; color:var(--allstar-text) !important;
    font-weight:750; white-space:normal; text-align:center; line-height:1.2;
    transition:background-color .15s ease, border-color .15s ease, color .15s ease, box-shadow .15s ease;
}
[data-baseweb="tab-list"] [data-baseweb="tab"]:hover, [role="tablist"] [data-testid="stTab"]:hover {
    border-color:var(--allstar-selected) !important; background:var(--allstar-card) !important;
}
[data-baseweb="tab-list"] [aria-selected="true"], [role="tablist"] [data-testid="stTab"][aria-selected="true"] {
    color:var(--allstar-selected-text) !important; background:var(--allstar-selected) !important;
    border-color:var(--allstar-selected) !important; box-shadow:0 4px 12px rgba(36,95,166,.24);
}
[data-baseweb="tab-list"] [aria-selected="true"] p,
[role="tablist"] [data-testid="stTab"][aria-selected="true"] p {color:var(--allstar-selected-text) !important;}
[data-baseweb="tab-highlight"] {display:none !important;}
[data-baseweb="tab-border"] {display:none !important;}
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"] {
    background-color:var(--allstar-surface) !important; color:var(--allstar-text) !important;
    border:1px solid transparent !important; isolation:isolate; overflow:hidden;
}
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"]::before {
    content:""; position:absolute; inset:-1px; z-index:0; pointer-events:none;
    border-radius:9px; background:var(--allstar-surface);
    box-shadow:inset 0 0 0 1px var(--allstar-border);
}
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"] > * {
    position:relative; z-index:1; color:var(--allstar-text) !important;
}
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"][data-selected],
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"][aria-selected="true"] {
    background-color:var(--allstar-selected) !important; color:var(--allstar-selected-text) !important;
    border-color:var(--allstar-selected) !important; box-shadow:0 4px 12px rgba(36,95,166,.24) !important;
}
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"][data-selected]::before,
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"][aria-selected="true"]::before {
    background:var(--allstar-selected); box-shadow:inset 0 0 0 1px var(--allstar-selected);
}
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"][data-selected] > *,
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"][aria-selected="true"] > * {
    color:var(--allstar-selected-text) !important;
}
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"][data-selected] p,
.stApp [data-testid="stTabs"] [role="tablist"] > [data-testid="stTab"][aria-selected="true"] p {
    color:var(--allstar-selected-text) !important;
}
.stApp [data-testid="stTabs"] .react-aria-SelectionIndicator {display:none !important;}
/* 다섯 번째 상위 탭부터 오른쪽 QA 영역으로 분리한다. */
[data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
  [data-baseweb="tab"]:nth-child(5),
[data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
  button[role="tab"]:nth-child(5) {
    margin-left:auto !important;
    padding-left:2rem !important;
    border-left:1px solid var(--allstar-border) !important;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stTabs"] > div > [role="tablist"]
  > [data-testid="stTab"]:nth-child(5) {
    margin-left:auto !important; padding-left:2rem !important; border-left:1px solid var(--allstar-border) !important;
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
.profile-card-stack {display:flex; flex-direction:column; width:100%;}
.profile-status-slot {box-sizing:border-box; height:2rem; display:flex; align-items:center; margin:0 0 .35rem;}
.profile-status-badge {display:inline-block; padding:.18rem .58rem; border-radius:999px; color:#fff; font-size:.78rem; font-weight:800;}
.profile-status-running, .profile-status-selected {background:#2f80ed;}
.profile-status-completed {background:#d97706;}
.profile-execution-card {height:17rem; padding-bottom:14px;}
.profile-card.profile-running,
.profile-card.profile-selected {
    border:2px solid #2f80ed; background:linear-gradient(145deg, rgba(47,128,237,.22), var(--allstar-card));
    box-shadow:0 0 0 3px rgba(47,128,237,.12), 0 8px 22px rgba(47,128,237,.14);
}
.profile-card.profile-completed {
    border:2px solid #d97706; background:linear-gradient(145deg, rgba(217,119,6,.20), var(--allstar-card));
    box-shadow:0 0 0 3px rgba(217,119,6,.10);
}
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
[class*="st-key-ai_chat_panel"] {gap:0 !important;}
[class*="st-key-ai_chat_panel"] > div {gap:0 !important;}
[class*="st-key-ai_chat_panel"] [data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px 12px 0 0 !important;}
[class*="st-key-ai_chat_panel"] [data-testid="stChatInput"] {border-radius:0 0 12px 12px !important; margin-top:-1px;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    width:fit-content !important; max-width:82%; margin-left:auto; flex-direction:row-reverse;
    border:1px solid rgba(47,128,237,.26); background:rgba(47,128,237,.10) !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {text-align:right;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    width:fit-content !important; max-width:82%; margin-right:auto;
    border:1px solid var(--allstar-border); background:var(--allstar-card) !important;
}
.ai-typing-indicator {font-weight:750; color:var(--allstar-muted);}
.ai-typing-indicator span {display:inline-block; min-width:1.2rem; animation:allstar-typing 1.2s steps(4,end) infinite; overflow:hidden; vertical-align:bottom;}
@keyframes allstar-typing {0% {width:0;} 100% {width:1.2rem;}}
.quality-score-help {margin-top:.55rem; padding:.7rem .8rem; border:1px solid var(--allstar-border); border-radius:10px; background:var(--allstar-card); color:var(--allstar-muted); font-size:.82rem; line-height:1.55;}
.stage-detail {border:1px solid var(--allstar-border); border-radius:12px; padding:1rem; background:var(--allstar-card);}
.stage-node {box-sizing:border-box; width:180px; min-height:112px; border:1px solid var(--allstar-border); border-radius:12px; padding:.65rem .55rem; background:var(--allstar-card); text-align:center; display:flex; flex-direction:column; justify-content:center;}
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
.stage-no_data {border-color:#c07a12; background:rgba(192,122,18,.13);}
.stage-no_data em {color:#c07a12;}
.stage-arrow {display:flex; width:26px; min-height:112px; align-items:center; justify-content:center; color:var(--allstar-muted); font-size:1.3rem; font-weight:900; text-align:center;}
.stage-button-arrow {display:flex; width:26px; height:4.5rem; align-items:center; justify-content:center; color:var(--allstar-muted); font-size:1.25rem; font-weight:900;}
[class*="st-key-stage_scroll_progress_"] {overflow-x:auto; overflow-y:hidden; padding-bottom:1rem;}
[class*="st-key-stage_scroll_interactive_"] {overflow-x:auto; overflow-y:hidden; padding-bottom:.2rem;}
[class*="st-key-stage_scroll_progress_"] > div,
[class*="st-key-stage_scroll_interactive_"] > div {min-width:max-content; gap:.35rem !important;}
[class*="st-key-stage_top_"] [data-testid="stHorizontalBlock"],
[class*="st-key-stage_buttons_"] [data-testid="stHorizontalBlock"] {flex-wrap:nowrap !important; gap:.38rem !important; min-width:max-content;}
[class*="st-key-stage_top_cell_"],
[class*="st-key-stage_cell_"] {flex:0 0 auto !important; width:180px !important; min-width:180px !important; max-width:180px !important;}
[class*="st-key-stage_top_cell_"] > div,
[class*="st-key-stage_cell_"] > div {width:180px !important; min-width:180px !important;}
[class*="st-key-stage_buttons_"] [data-testid="stButton"] {width:180px !important; min-width:180px !important;}
[class*="st-key-stage_buttons_"] [data-testid="stButton"] button {
    width:180px !important; min-width:180px !important; height:4.5rem !important; padding:.55rem .45rem !important;
}
[class*="st-key-stage_buttons_"] [data-testid="stButton"] button p {
    width:100% !important; white-space:pre-line !important; word-break:keep-all !important;
    overflow-wrap:normal !important; hyphens:none !important; line-height:1.35 !important;
}
[class*="st-key-stage_top_arrow_"],
[class*="st-key-stage_arrow_"] {flex:0 0 auto !important; width:26px !important; min-width:26px !important; max-width:26px !important;}
[class*="st-key-stage_top_arrow_"] > div,
[class*="st-key-stage_arrow_"] > div {width:26px !important; min-width:26px !important;}
/* 부분 갱신 중 기존 화면 전체가 회색으로 흐려지는 Streamlit stale 효과를 제거한다. */
[data-stale="true"] {opacity:1 !important;}
@media (max-width:1200px) {
    .block-container {padding-left:1.2rem !important; padding-right:1.2rem !important;}
    .profile-card {height:19rem;}
    .profile-execution-card {height:19rem;}
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      [data-baseweb="tab"]:nth-child(5),
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      button[role="tab"]:nth-child(5) {margin-left:1rem !important; padding-left:1rem !important;}
}
@media (max-width:900px) {
    .block-container {padding-left:.8rem !important; padding-right:.8rem !important; padding-top:.65rem;}
    .allstar-banner {padding:.85rem 1rem; border-radius:11px;}
    .allstar-banner h1 {font-size:1.35rem;}
    .allstar-banner p {font-size:.88rem; line-height:1.45;}
    .profile-card {height:auto; min-height:0; overflow-y:visible; padding:10px 12px;}
    .profile-status-slot.is-empty {display:none;}
    .profile-status-slot:not(.is-empty) {height:auto; min-height:1.65rem; margin-bottom:.3rem;}
    .profile-title, .profile-summary {min-height:0;}
    .profile-summary {margin-bottom:.55rem;}
    .profile-model {margin-top:.25rem;}
    [data-baseweb="tab-list"], [role="tablist"] {overflow-x:auto; flex-wrap:nowrap; gap:.3rem !important; padding:.3rem !important;}
    [data-baseweb="tab-list"] [data-baseweb="tab"], [role="tablist"] [data-testid="stTab"] {
        min-width:7.6rem; min-height:3rem; padding:.55rem .72rem !important; font-size:.88rem;
    }
    [class*="st-key-ai_live_breakdown_comparison"] [data-testid="stHorizontalBlock"],
    [class*="st-key-ai_batch_breakdown_comparison"] [data-testid="stHorizontalBlock"] {flex-direction:column !important;}
    [class*="st-key-ai_live_breakdown_comparison"] [data-testid="column"],
    [class*="st-key-ai_batch_breakdown_comparison"] [data-testid="column"] {width:100% !important; flex:1 1 100% !important;}
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      [data-baseweb="tab"]:nth-child(5),
    [data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"])
      button[role="tab"]:nth-child(5) {margin-left:0 !important; padding-left:.9rem !important; border-left:0 !important;}
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stTabs"] > div > [role="tablist"]
      > [data-testid="stTab"]:nth-child(5) {margin-left:0 !important; padding-left:.9rem !important; border-left:0 !important;}
}
@media (max-width:600px) {
    .block-container {padding-left:.45rem !important; padding-right:.45rem !important;}
    .allstar-banner {margin-bottom:.55rem; padding:.75rem .85rem;}
    .allstar-banner h1 {font-size:1.18rem;}
    .allstar-banner p {font-size:.8rem;}
    [data-baseweb="tab-list"] [data-baseweb="tab"], [role="tablist"] [data-testid="stTab"] {min-width:7rem; font-size:.82rem;}
    .scope-box {padding:.7rem .75rem; font-size:.88rem; line-height:1.5;}
    [data-testid="stChatMessage"] {max-width:92% !important;}
    [data-testid="stHorizontalBlock"] {gap:.55rem;}
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
