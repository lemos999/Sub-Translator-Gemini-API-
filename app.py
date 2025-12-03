# filename: app.py

import streamlit as st
import google.generativeai as genai
import time
import datetime

# 모듈화된 파일들 임포트
import config
import core
import ui

# [세션 상태(Session State) 초기화]
def init_session_state():
    """애플리케이션의 상태 변수들을 초기화한다."""
    defaults = {
        "chunks": [], "results": [], "debugs": [], "parsed_srt": [], "chunk_states": [],
        "is_running": False, "context_guide": "", "final_srt_content": "", "fetched_models": []
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# [메인 애플리케이션 함수]
def main():
    """메인 애플리케이션 로직을 실행한다."""
    st.set_page_config(page_title="Ray's Subtitle Translator", layout="wide")
    ui.load_css()
    init_session_state()

    # --- 사이드바 렌더링 및 이벤트 처리 ---
    event, settings = ui.render_sidebar()
    api_key = settings.get("api_key")

    if event == "check_models":
        if not api_key:
            st.error("API Key Required")
        else:
            try:
                genai.configure(api_key=api_key)
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                st.session_state["fetched_models"] = models
                st.success(f"Found {len(models)} models!")
                st.rerun() # 모델 목록을 즉시 UI에 반영하기 위해 새로고침
            except Exception as e:
                st.error(f"Error: {e}")
    
    elif event == "stop_process":
        st.session_state["is_running"] = False
        st.warning("Stopping process... Please wait.")
        st.rerun()

    # --- 메인 페이지 UI 구성 ---
    st.title("🎬 Subtitle Translator (Context-Aware)")
    uploaded_file = st.file_uploader("Upload Subtitle (.srt)", type=["srt"])

    if not uploaded_file:
        st.info("👈 Please upload an SRT file to begin.")
        return

    if not api_key or not settings.get("selected_model"):
        st.warning("👈 Please enter your API Key and select a model in the sidebar.")
        return

    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to configure API Key: {e}")
        return

    # 파일 처리
    content = st.session_state.get("original_content")
    if not content:
        bytes_data = uploaded_file.getvalue()
        encoding = core.detect_encoding(bytes_data) or 'utf-8'
        try:
            content = bytes_data.decode(encoding)
        except:
            content = bytes_data.decode('utf-8', errors='ignore')
        st.session_state["original_content"] = content
    st.info(f"File loaded. Encoding: {st.session_state.get('encoding', 'unknown')}")

    # --- 컨텍스트 분석 (Step 1) ---
    st.divider()
    st.subheader("🕵️ Step 1: Context Analysis (Optional)")
    col_a1, col_a2 = st.columns([1, 4])
    if col_a1.button("🧠 Analyze Context"):
        with st.spinner("Analyzing..."):
            model = genai.GenerativeModel(settings["selected_model"])
            st.session_state["context_guide"] = core.analyze_context(model, content, settings["src_lang"], settings["tgt_lang"])
        st.success("Analysis Done!")
    
    st.session_state["context_guide"] = col_a2.text_area("Context Guide:", st.session_state["context_guide"], height=150)
    
    # --- 번역 실행 (Step 2) ---
    st.divider()
    st.subheader("🚀 Step 2: Start Translation")
    if st.button("Start Translation Process", type="primary"):
        run_translation(content, settings)

    # --- 결과 및 수리(Repair) 화면 ---
    if st.session_state.get("final_srt_content"):
        render_results_and_repair(content, settings)

def run_translation(content, settings):
    """번역 프로세스를 시작하고 실행하는 함수."""
    parsed = core.parse_srt(content)
    if not parsed:
        st.error("SRT parsing failed.")
        return

    st.session_state.update({
        "is_running": True, "parsed_srt": parsed,
        "chunks": core.chunk_text(parsed, settings["chunk_size"]),
    })
    
    total = len(st.session_state["chunks"])
    st.session_state.update({
        "results": [None] * total, "debugs": [None] * total,
        "chunk_states": [{'status': 'WAITING', 'duration': 0} for _ in range(total)]
    })

    # UI প্লেস홀더
    timer_ph, grid_ph, status_ph = st.empty(), st.empty(), st.empty()
    model = genai.GenerativeModel(settings["selected_model"])
    start_global = time.time()
    
    for i, chunk in enumerate(st.session_state["chunks"]):
        if not st.session_state["is_running"]:
            status_ph.warning(f"Stopped at Chunk {i}.")
            break
        
        st.session_state["chunk_states"][i]['status'] = 'RUNNING'
        with grid_ph.container(): ui.render_grid(st.session_state["chunk_states"])
        status_ph.info(f"⚡ Processing Chunk {i+1}/{total}...")
        
        elapsed = time.time() - start_global
        avg_time = elapsed / (i + 1)
        eta = avg_time * (total - (i + 1))
        
        texts = [item['text'] for item in chunk]
        res, debug = core.translate_chunk(model, texts, **settings)
        
        st.session_state["results"][i] = res
        st.session_state["debugs"][i] = debug
        st.session_state["chunk_states"][i]['status'] = 'SUCCESS' if debug['status'] == "Success" else 'ERROR'
        st.session_state["chunk_states"][i]['duration'] = debug.get('duration', 0)
        
    st.session_state["is_running"] = False
    st.session_state["final_srt_content"] = core.rebuild_srt(st.session_state["parsed_srt"], st.session_state["results"])
    st.rerun()

def render_results_and_repair(content, settings):
    """번역 완료 후 결과와 수리 UI를 렌더링하는 함수."""
    st.divider()
    st.subheader("📊 Execution Overview")
    ui.render_grid(st.session_state["chunk_states"])
    
    col_l, col_r = st.columns(2)
    col_l.text_area("Original", content, height=400)
    col_r.text_area("Translated", st.session_state["final_srt_content"], height=400)
        
    st.download_button("Download Result (.srt)", st.session_state["final_srt_content"].encode('utf-8'),
                        f"translated_{st.session_state.get('uploaded_filename', 'file.srt')}", type="primary")
    
    st.divider()
    st.subheader("🛠️ Chunk Inspector")
    
    for i, debug in enumerate(st.session_state["debugs"]):
        if debug is None: continue
        is_success = debug['status'] == "Success"
        with st.expander(f"{'✅' if is_success else '❌'} Chunk {i+1}", expanded=not is_success):
            if st.button(f"🔄 Retry #{i+1}", key=f"retry_{i}"):
                with st.spinner(f"Retrying..."):
                    model = genai.GenerativeModel(settings["selected_model"])
                    texts = [item['text'] for item in st.session_state["chunks"][i]]
                    res, new_debug = core.translate_chunk(model, texts, **settings)
                    
                    # Update states
                    st.session_state["results"][i] = res
                    st.session_state["debugs"][i] = new_debug
                    st.session_state["chunk_states"][i].update({
                        'status': 'SUCCESS' if new_debug['status'] == "Success" else 'ERROR',
                        'duration': new_debug.get('duration', 0)
                    })
                    st.session_state["final_srt_content"] = core.rebuild_srt(st.session_state["parsed_srt"], st.session_state["results"])
                    st.rerun()

# --- 애플리케이션 실행 ---
if __name__ == "__main__":
    main()