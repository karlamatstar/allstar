from __future__ import annotations

import streamlit as st

from allstar.ui.dashboard.views import (
    render_ai_chat,
    render_ai_testcases,
    render_k6_load_test,
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
    --allstar-positive:#188a4c;
    --allstar-positive-hover:#126f3d;
    --allstar-danger:#c0392b;
    --allstar-danger-hover:#9f2f24;
    --allstar-disabled:#a8b1bf;
    --allstar-disabled-border:#949eac;
    --allstar-disabled-text:#f8fafc;
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
        --allstar-positive:#229a58;
        --allstar-positive-hover:#1a7d48;
        --allstar-danger:#d94b40;
        --allstar-danger-hover:#b93b32;
        --allstar-disabled:#596474;
        --allstar-disabled-border:#6b7789;
        --allstar-disabled-text:#d7dee8;
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

/* 버튼은 문구 의미와 상태를 같은 색으로 유지한다. */
.stApp [data-testid="stBaseButton-primary"] {
    background:var(--allstar-positive) !important; border-color:var(--allstar-positive) !important;
    color:#fff !important; font-weight:800 !important;
}
.stApp [data-testid="stBaseButton-primary"] * {color:#fff !important;}
.stApp [data-testid="stBaseButton-primary"]:hover {
    background:var(--allstar-positive-hover) !important; border-color:var(--allstar-positive-hover) !important;
}
.stApp [class*="st-key-stop_"] button,
.stApp [class*="st-key-ai_fault_"] button,
.stApp [class*="st-key-ai_delete_button"] button,
.stApp [class*="st-key-voc_delete_button"] button {
    background:var(--allstar-danger) !important; border-color:var(--allstar-danger) !important;
    color:#fff !important; font-weight:800 !important;
}
.stApp [class*="st-key-stop_"] button *,
.stApp [class*="st-key-ai_fault_"] button *,
.stApp [class*="st-key-ai_delete_button"] button *,
.stApp [class*="st-key-voc_delete_button"] button * {color:#fff !important;}
.stApp [class*="st-key-stop_"] button:hover,
.stApp [class*="st-key-ai_fault_"] button:hover,
.stApp [class*="st-key-ai_delete_button"] button:hover,
.stApp [class*="st-key-voc_delete_button"] button:hover {
    background:var(--allstar-danger-hover) !important; border-color:var(--allstar-danger-hover) !important;
}
.stApp [class*="st-key-voc_chat_profile_"] button:not(:disabled),
.stApp [class*="st-key-stage_buttons_"] [data-testid="stBaseButton-primary"] {
    background:var(--allstar-selected) !important; border-color:var(--allstar-selected) !important;
    color:var(--allstar-selected-text) !important; font-weight:800 !important;
}
.stApp [class*="st-key-voc_chat_profile_"] button:not(:disabled) *,
.stApp [class*="st-key-stage_buttons_"] [data-testid="stBaseButton-primary"] * {
    color:var(--allstar-selected-text) !important;
}
.stApp button:disabled,
.stApp [data-testid^="stBaseButton"]:disabled,
.stApp [class*="st-key-stop_"] button:disabled,
.stApp [class*="st-key-ai_fault_"] button:disabled,
.stApp [class*="st-key-ai_delete_button"] button:disabled,
.stApp [class*="st-key-voc_delete_button"] button:disabled {
    background:var(--allstar-disabled) !important; border-color:var(--allstar-disabled-border) !important;
    color:var(--allstar-disabled-text) !important; opacity:1 !important; cursor:not-allowed !important;
    box-shadow:none !important;
}
.stApp button:disabled * {color:var(--allstar-disabled-text) !important; opacity:1 !important;}

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
.profile-status-completed {background:var(--allstar-positive);}
.profile-execution-card {height:17rem; padding-bottom:14px;}
.profile-card.profile-running,
.profile-card.profile-selected {
    border:2px solid #2f80ed; background:linear-gradient(145deg, rgba(47,128,237,.22), var(--allstar-card));
    box-shadow:0 0 0 3px rgba(47,128,237,.12), 0 8px 22px rgba(47,128,237,.14);
}
.profile-card.profile-completed {
    border:2px solid var(--allstar-positive); background:linear-gradient(145deg, rgba(24,138,76,.16), var(--allstar-card));
    box-shadow:0 0 0 3px rgba(24,138,76,.10);
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
[class*="st-key-ai_chat_panel"], [class*="st-key-voc_chat_panel"] {gap:0 !important;}
[class*="st-key-ai_chat_panel"] > div, [class*="st-key-voc_chat_panel"] > div {gap:0 !important;}
[class*="st-key-ai_chat_panel"] > [data-testid="stLayoutWrapper"],
[class*="st-key-voc_chat_panel"] > [data-testid="stLayoutWrapper"] {
    border:2px solid var(--allstar-selected) !important; border-radius:12px 12px 0 0 !important;
    background:var(--allstar-surface) !important; box-shadow:0 5px 16px rgba(36,95,166,.13);
}
[class*="st-key-ai_chat_panel"] [data-testid="stVerticalBlockBorderWrapper"],
[class*="st-key-voc_chat_panel"] [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius:12px 12px 0 0 !important; border-width:2px !important;
    border-color:var(--allstar-selected) !important; box-shadow:0 5px 16px rgba(36,95,166,.13);
}
[class*="st-key-ai_chat_panel"] [data-testid="stChatInput"],
[class*="st-key-voc_chat_panel"] [data-testid="stChatInput"] {
    border:2px solid var(--allstar-selected) !important; border-radius:0 0 12px 12px !important;
    margin-top:-2px; background:var(--allstar-input) !important;
    box-shadow:0 5px 16px rgba(36,95,166,.16) !important;
}
[class*="st-key-ai_chat_panel"] [data-testid="stChatInput"]:focus-within,
[class*="st-key-voc_chat_panel"] [data-testid="stChatInput"]:focus-within {
    border-color:var(--allstar-positive) !important; box-shadow:0 0 0 4px rgba(24,138,76,.16) !important;
}
[class*="st-key-ai_chat_panel"] [data-testid="stChatInput"] textarea,
[class*="st-key-voc_chat_panel"] [data-testid="stChatInput"] textarea {
    font-size:1rem !important; font-weight:650 !important; min-height:3.25rem !important;
}
.chat-input-guide {
    box-sizing:border-box; height:2.25rem; margin:0; padding:0 .78rem;
    display:flex; align-items:center; line-height:1.1;
    border-left:2px solid var(--allstar-selected);
    border-right:2px solid var(--allstar-selected); background:rgba(47,128,237,.10);
    color:var(--allstar-text); font-size:.82rem; font-weight:850;
}
[data-testid="stElementContainer"]:has(.chat-input-guide),
[data-testid="stMarkdown"]:has(.chat-input-guide),
[data-testid="stMarkdownContainer"]:has(.chat-input-guide) {
    min-height:2.25rem !important; height:2.25rem !important;
}
[class*="st-key-ai_chat_server_stopping_notice"],
[class*="st-key-ai_chat_server_down_notice"],
[class*="st-key-ai_chat_server_recovered_notice"],
[class*="st-key-voc_chat_server_down_notice"],
[class*="st-key-voc_chat_server_recovered_notice"] {
    box-sizing:border-box; width:min(100%, 640px); margin:1rem auto !important;
    text-align:center;
}
[class*="st-key-ai_chat_server_stopping_notice"] [data-testid="stVerticalBlockBorderWrapper"] {
    border-color:rgba(245,158,11,.65) !important; background:rgba(245,158,11,.10) !important;
}
[class*="st-key-ai_chat_server_down_notice"] [data-testid="stVerticalBlockBorderWrapper"],
[class*="st-key-voc_chat_server_down_notice"] [data-testid="stVerticalBlockBorderWrapper"] {
    border-color:rgba(239,68,68,.72) !important; background:rgba(239,68,68,.10) !important;
}
[class*="st-key-ai_chat_server_recovered_notice"] [data-testid="stVerticalBlockBorderWrapper"],
[class*="st-key-voc_chat_server_recovered_notice"] [data-testid="stVerticalBlockBorderWrapper"] {
    border-color:rgba(34,197,94,.65) !important; background:rgba(34,197,94,.10) !important;
}
.ai-server-status-title {font-size:1.05rem; font-weight:900; color:var(--allstar-text); margin:.15rem 0 .45rem;}
.ai-server-status-message {color:var(--allstar-muted); line-height:1.55; margin:0 0 .75rem;}
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
.k6-env-grid {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.65rem; margin-bottom:.55rem;}
.k6-env-item {border:1px solid var(--allstar-border); border-radius:12px; padding:.72rem .82rem; background:var(--allstar-card); display:flex; flex-direction:column; gap:.15rem;}
.k6-env-item b {display:flex; align-items:center; gap:.42rem; font-size:.9rem;}
.k6-env-item b span {width:.7rem; height:.7rem; border-radius:50%; background:#8b95a5; box-shadow:0 0 0 3px rgba(139,149,165,.14);}
.k6-env-ready b span {background:#188a4c; box-shadow:0 0 0 3px rgba(24,138,76,.14);}
.k6-env-offline b span {background:#8b95a5;}
.k6-env-item strong {font-size:.8rem; color:var(--allstar-muted);}
.k6-env-item small {font-size:.74rem; color:var(--allstar-muted); overflow-wrap:anywhere;}
[class*="st-key-k6_card_row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
    align-items:stretch !important;
}
[class*="st-key-k6_card_row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    display:flex !important;
}
[class*="st-key-k6_card_row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {
    width:100%; height:100%;
}
[class*="st-key-k6_card_row_"] [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-k6_card_"]) {
    flex:1 1 auto !important; height:100%;
}
[class*="st-key-k6_card_"] {height:100%; min-height:25.5rem;}
[class*="st-key-k6_card_"] [data-testid="stVerticalBlockBorderWrapper"] {height:100%; min-height:25.5rem; border-radius:14px !important; background:var(--allstar-card) !important;}
[class*="st-key-k6_card_"] [data-testid="stVerticalBlock"] {height:100%;}
[class*="st-key-k6_card_"] > [class*="st-key-run_k6_"] {margin-top:auto;}
[class*="st-key-k6_card_"] [data-testid="stNumberInputContainer"] {
    display:grid !important;
    grid-template-columns:2.35rem minmax(0,1fr) 2.35rem !important;
    align-items:stretch !important;
    overflow:hidden;
}
[class*="st-key-k6_card_"] [data-testid="stNumberInputField"] {
    grid-column:2 !important;
    grid-row:1 !important;
    min-width:0 !important;
    width:100% !important;
    text-align:center !important;
}
[class*="st-key-k6_card_"] [data-testid="stNumberInputContainer"] > div:has(> [data-testid="stNumberInputStepDown"]) {
    display:contents !important;
}
[class*="st-key-k6_card_"] [data-testid="stNumberInputStepDown"],
[class*="st-key-k6_card_"] [data-testid="stNumberInputStepUp"] {
    grid-row:1 !important;
    width:100% !important;
    height:100% !important;
    min-height:2.5rem !important;
    border-radius:0 !important;
}
[class*="st-key-k6_card_"] [data-testid="stNumberInputStepDown"] {
    grid-column:1 !important;
    border-right:1px solid var(--allstar-border) !important;
}
[class*="st-key-k6_card_"] [data-testid="stNumberInputStepUp"] {
    grid-column:3 !important;
    border-left:1px solid var(--allstar-border) !important;
}
[class*="st-key-k6_card_"][class*="_running"] [data-testid="stVerticalBlockBorderWrapper"] {border:2px solid #2f80ed !important; background:linear-gradient(145deg,rgba(47,128,237,.18),var(--allstar-card)) !important; box-shadow:0 0 0 3px rgba(47,128,237,.10);}
[class*="st-key-k6_card_"][class*="_completed"] [data-testid="stVerticalBlockBorderWrapper"] {border:2px solid #188a4c !important; background:linear-gradient(145deg,rgba(24,138,76,.13),var(--allstar-card)) !important;}
[class*="st-key-k6_card_"][class*="_failed"] [data-testid="stVerticalBlockBorderWrapper"],
[class*="st-key-k6_card_"][class*="_cancelled"] [data-testid="stVerticalBlockBorderWrapper"] {border:2px solid var(--allstar-danger) !important; background:linear-gradient(145deg,rgba(192,57,43,.13),var(--allstar-card)) !important;}
.k6-card-status {height:1.8rem; display:flex; align-items:center;}
.k6-card-status-empty {visibility:hidden;}
.k6-card-badge {display:inline-block; padding:.18rem .58rem; border-radius:999px; color:#fff; font-size:.76rem; font-weight:850;}
.k6-card-badge-running {background:#2f80ed;}
.k6-card-badge-completed {background:#188a4c;}
.k6-card-badge-failed,.k6-card-badge-cancelled {background:var(--allstar-danger);}
.k6-card-copy h4 {margin:.05rem 0 0; font-size:1.02rem;}
.k6-card-english {color:var(--allstar-muted); font-size:.82rem; font-weight:750; margin:.1rem 0 .65rem;}
.k6-card-copy p {min-height:4.8rem; color:var(--allstar-muted); font-size:.86rem; line-height:1.5;}
.k6-card-copy hr {border:0; border-top:1px solid var(--allstar-border); margin:.65rem 0;}
.k6-card-copy small {display:block; min-height:2.4rem; color:var(--allstar-muted); font-size:.76rem; line-height:1.45;}
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
@media (max-width:1399px) and (min-width:761px) {
    [class*="st-key-k6_card_row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
        flex-wrap:wrap !important;
    }
    [class*="st-key-k6_card_row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex:1 1 calc(50% - 1.1rem) !important;
        width:calc(50% - 1.1rem) !important;
        min-width:calc(50% - 1.1rem) !important;
        max-width:calc(50% - 1.1rem) !important;
    }
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
    .k6-env-grid {grid-template-columns:repeat(2,minmax(0,1fr));}
}
@media (max-width:760px) {
    [class*="st-key-k6_card_row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
        flex-wrap:wrap !important;
    }
    [class*="st-key-k6_card_row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex:1 1 100% !important; width:100% !important; min-width:100% !important; max-width:100% !important;
    }
    [class*="st-key-k6_card_"] {min-height:0;}
    [class*="st-key-k6_card_"] [data-testid="stVerticalBlockBorderWrapper"] {min-height:0;}
    .k6-card-copy p,.k6-card-copy small {min-height:0;}
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
    .k6-env-grid {grid-template-columns:1fr;}
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
    tab_k6_load,
    tab_ai_cases,
    tab_voc_cases,
) = st.tabs(
    [
        "AI 에이전트 챗봇\n(AI Agent)",
        "VOC 챗봇\n(VOC)",
        "모니터링\n(Monitoring)",
        "보고서 모음\n(Reports)",
        "K6 부하 테스트\n(K6 Load Test)",
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

with tab_k6_load:
    render_k6_load_test()

with tab_ai_cases:
    render_ai_testcases()

with tab_voc_cases:
    render_voc_testcases()
