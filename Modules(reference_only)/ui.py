# filename: ui.py

# -----------------------------------------------------------------------------
# [UI 헬퍼 모듈]
# 이 파일은 Streamlit UI를 구성하는 복잡하거나 반복적인 코드들을 함수로 캡슐화한다.
# 메인 파일(app.py)의 가독성을 높이고, UI 관련 코드를 한 곳에서 관리하기 위함이다.
# -----------------------------------------------------------------------------

import streamlit as st
import config # 설정 파일 임포트

def load_css():
    """애플리케이션 전체에 적용될 커스텀 CSS를 로드한다."""
    st.markdown(f"""
    <style>
        /* 사이드바 최소/최대 너비 지정 */
        [data-testid="stSidebar"] {{ min-width: 350px; max-width: 500px; }}
        /* 모든 버튼 스타일 통일 */
        .stButton>button {{ width: 100%; border-radius: 8px; font-weight: bold; }}
        /* 대시보드 메트릭 박스 스타일 */
        .metric-box {{ border: 1px solid #ddd; padding: 10px; border-radius: 8px; text-align: center; background: #fdfdfd; }}
        .metric-val {{ font-size: 1.5em; font-weight: bold; color: #333; }}
        .metric-label {{ font-size: 0.9em; color: #666; }}
        /* 깃허브 아이콘 링크 스타일 */
        .github-link {{ text-decoration: none; color: #fafafa; }}
        .github-icon svg {{ width: 20px; height: 20px; fill: currentColor; margin-right: 8px; vertical-align: middle; transition: color 0.2s; }}
        .github-link:hover {{ color: #3b82f6; }}
        /* 푸터 스타일 */
        .footer {{ font-size: 0.8em; color: #aaa; text-align: center; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar():
    """
    사이드바 UI 전체를 렌더링하고, 사용자 입력과 이벤트를 반환한다.
    
    Returns:
        tuple: (이벤트 이름, 설정 딕셔너리)
    """
    with st.sidebar:
        # 깃허브 링크
        st.markdown(f"""
        <a href="{config.GITHUB_URL}" target="_blank" class="github-link">
            <span class="github-icon">{config.GITHUB_ICON_SVG}</span>
            {config.AUTHOR_NAME}'s GitHub
        </a>
        """, unsafe_allow_html=True)
        
        st.header("⚙️ Settings")
        api_key = st.text_input("Google API Key", type="password")
        
        # '모델 조회' 버튼이 눌리면 "check_models" 이벤트를 반환.
        if st.button("🔍 Check Models"):
            return "check_models", {"api_key": api_key}
        
        # 나머지 설정들을 하나의 딕셔너리로 묶어 관리.
        settings = {
            "api_key": api_key,
            "selected_model": None,
            "chunk_size": st.slider("Chunk Size", config.CHUNK_SIZE_MIN, config.CHUNK_SIZE_MAX, config.CHUNK_SIZE_DEFAULT, config.CHUNK_SIZE_STEP),
            "enable_reasoning": st.toggle("Enable Reasoning Bucket (Max)", value=False, help="ON: 더 깊게 생각하고 번역합니다 (속도 느림). OFF: Auto"),
            "src_lang": st.selectbox("From", config.LANGUAGE_OPTIONS),
            "tgt_lang": st.selectbox("To", config.LANGUAGE_OPTIONS, index=1)
        }
        
        # 모델 목록이 세션에 저장되어 있으면 드롭다운을 표시.
        if "fetched_models" in st.session_state and st.session_state["fetched_models"]:
            # 이전에 선택했던 모델이 있으면 유지하고, 없으면 기본값(flash/pro)으로 설정
            current_model_list = st.session_state["fetched_models"]
            try:
                index = current_model_list.index(settings["selected_model"]) if settings["selected_model"] in current_model_list else 0
            except ValueError:
                index = 0 # 기본값 fallback
            
            settings["selected_model"] = st.selectbox("Select Model", current_model_list, index=index, format_func=lambda x: x.replace("models/", ""))
        else:
            st.selectbox("Select Model", [], disabled=True)
            
        st.divider()
        # 작업 중일 때만 '긴급 정지' 버튼을 표시.
        if st.session_state.get("is_running", False):
            if st.button("🚨 STOP PROCESS", type="primary"):
                return "stop_process", settings
        
        st.markdown(f'<div class="footer">{config.CREDITS}</div>', unsafe_allow_html=True)
        # 특별한 이벤트가 없으면, 현재 설정값을 업데이트하라는 의미로 "update_settings" 반환.
        return "update_settings", settings

def render_grid(states):
    """청크 상태 그리드 HTML을 생성하고 화면에 출력한다."""
    grid_style = """
    <style>
        .grid-container { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 20px; }
        .grid-item { width: 12px; height: 12px; border-radius: 2px; }
        .grid-item:hover { transform: scale(1.5); z-index: 10; cursor: help; border: 1px solid #fff; }
        .status-WAITING { background-color: #e5e7eb; } .status-RUNNING { background-color: #3b82f6; box-shadow: 0 0 5px #3b82f6; animation: pulse 1s infinite; }
        .status-SUCCESS { background-color: #22c55e; } .status-ERROR { background-color: #ef4444; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
    """
    grid_items = [f'<div class="grid-item status-{s.get("status", "WAITING")}" title="Chunk {i+1}: {s.get("status", "WAITING")} ({s.get("duration", 0)}s)"></div>' for i, s in enumerate(states)]
    st.markdown(grid_style + f'<div class="grid-container">{"".join(grid_items)}</div>', unsafe_allow_html=True)