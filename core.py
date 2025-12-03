# filename: core.py

# -----------------------------------------------------------------------------
# [1. 의존성 임포트]
# 이 애플리케이션을 구동하기 위해 필요한 모든 외부 및 내부 모듈을 선언한다.
# -----------------------------------------------------------------------------

# --- 외부 라이브러리 ---
import streamlit as st                 # 웹 UI 프레임워크. 화면의 모든 시각적 요소를 그리고 사용자 입력을 처리한다.
import google.generativeai as genai    # Google Gemini AI 모델과의 통신을 담당하는 공식 SDK.
import time                            # 시간 관련 함수. API 호출 사이의 지연(딜레이)이나 작업 소요 시간을 측정하는 데 사용.
import datetime                        # 날짜와 시간 객체를 다루는 라이브러리. '경과 시간'이나 '예상 종료 시간'을 사람이 보기 좋은 형태로 포맷팅한다.

# --- 내부 모듈 ---
# 우리가 직접 기능별로 분리한 모듈들을 불러온다. (모듈화의 증거)
import config                          # 고정된 설정값(URL, 이름, UI 옵션 등)을 모아둔 설정 파일.
import core                            # UI와 완전히 분리된, 순수 번역 로직의 핵심 엔진.
import ui                              # 복잡한 UI 컴포넌트(사이드바, 그리드 등)를 생성하는 함수들의 집합.


# -----------------------------------------------------------------------------
# [2. 애플리케이션 상태 관리]
# Streamlit의 핵심 메커니즘인 '재실행(rerun)'에 대응하기 위한 상태 관리.
# -----------------------------------------------------------------------------

def init_session_state():
    """
    애플리케이션의 모든 상태 변수를 초기화한다.
    Streamlit은 사용자 상호작용 시 스크립트 전체를 재실행하므로, 변수 값이 초기화되는 것을 막기 위해
    st.session_state 라는 특별한 '기억 공간' 또는 '금고'에 데이터를 보관해야 한다.
    이 함수는 앱이 처음 실행될 때 필요한 모든 '금고'의 칸을 미리 만들어두는 역할을 한다.
    """
    # 애플리케이션 전역에서 사용될 모든 상태 변수와 그 기본값을 딕셔너리로 정의.
    defaults = {
        "chunks": [],                   # 원본 텍스트를 나눈 청크들의 리스트.
        "results": [],                  # 각 청크의 번역 결과 리스트.
        "debugs": [],                   # 각 청크의 상세 디버그 정보 리스트.
        "parsed_srt": [],               # 원본 SRT 파일을 파싱한 구조체 리스트.
        "chunk_states": [],             # UI 시각화를 위한 각 청크의 상태(대기, 성공 등) 리스트.
        "is_running": False,            # 현재 번역 작업이 진행 중인지 여부를 나타내는 플래그(Flag).
        "context_guide": "",            # AI가 생성하고 사용자가 수정한 최종 컨텍스트 가이드.
        "final_srt_content": "",        # 번역 완료 후 최종적으로 조립된 SRT 파일 내용. 다운로드 버그 해결의 핵심.
        "fetched_models": [],           # API를 통해 조회한 사용 가능한 모델 목록.
        "original_content": None,       # 사용자가 업로드한 파일의 원본 내용.
        "uploaded_filename": None       # 현재 업로드된 파일의 이름. 파일 변경 감지용.
    }
    # defaults 딕셔너리를 순회하며, 세션 상태에 해당 키가 존재하지 않을 경우에만 기본값으로 초기화.
    # 이 조건문이 없으면, 사용자가 설정을 변경할 때마다 모든 상태가 초기화되는 대참사가 발생한다.
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# -----------------------------------------------------------------------------
# [3. 메인 애플리케이션 로직]
# 애플리케이션의 전체 흐름을 제어하는 함수들.
# -----------------------------------------------------------------------------

def main():
    """
    메인 애플리케이션 로직을 실행하는 진입점(Entry Point) 함수.
    전체 UI 구조를 정의하고, 사용자 이벤트에 따라 적절한 하위 함수를 호출하는 총괄 지휘자.
    """
    # st.set_page_config는 반드시 스크립트 실행 시 가장 먼저 호출되어야 하는 Streamlit의 규칙.
    st.set_page_config(page_title="Ray's Subtitle Translator", layout="wide")
    # 커스텀 CSS를 HTML 헤더에 주입.
    ui.load_css()
    # 세션 상태 변수들이 준비되었는지 확인하고, 없으면 생성.
    init_session_state()

    # --- 1. 사이드바 처리 ---
    # 사이드바 UI를 렌더링하고, 사용자의 현재 설정값(settings)과 발생한 이벤트(event)를 반환받는다.
    # 이 구조는 UI 코드와 로직 코드를 분리하여 app.py를 깔끔하게 유지한다.
    event, settings = ui.render_sidebar()
    api_key = settings.get("api_key")

    # 사이드바에서 발생한 이벤트에 따라 적절한 함수를 호출.
    if event == "check_models":
        handle_check_models(api_key)
    elif event == "stop_process":
        st.session_state["is_running"] = False
        st.warning("Stopping process... Please wait for the current chunk to finish.")
        st.rerun() # UI를 즉시 갱신 (예: 정지 버튼 숨기기)

    # --- 2. 메인 페이지 처리 ---
    st.title("🎬 Subtitle Translator (Context-Aware)")
    uploaded_file = st.file_uploader("Upload Subtitle (.srt)", type=["srt"])

    # [방어 코드 1] 파일이 업로드되지 않았으면, 더 이상 진행하지 않고 사용자에게 안내.
    if not uploaded_file:
        st.info("👈 Please upload an SRT file to begin.")
        return

    # [방어 코드 2] API 키나 모델이 준비되지 않았으면, 진행을 막고 안내.
    if not api_key or not settings.get("selected_model"):
        st.warning("👈 Please enter your API Key and select a model in the sidebar.")
        return

    # --- 3. 파일 내용 처리 및 캐싱 ---
    # 사용자가 동일한 파일을 계속 올려두고 다른 설정만 바꿀 때, 매번 파일을 다시 읽는 것은 비효율적.
    # 파일 이름이 변경되었을 때만 파일을 새로 읽고, 그렇지 않으면 세션에 저장된 내용을 재사용한다. (최적화)
    if uploaded_file.name != st.session_state.get("uploaded_filename"):
        st.session_state["uploaded_filename"] = uploaded_file.name
        bytes_data = uploaded_file.getvalue()
        encoding = core.detect_encoding(bytes_data) or 'utf-8' # 인코딩 감지 실패 시 utf-8로 안전하게 대체.
        st.session_state["encoding"] = encoding
        try:
            st.session_state["original_content"] = bytes_data.decode(encoding)
        except:
            # 최종 방어: 그래도 디코딩에 실패하면, 손상된 문자는 무시하고 강제로 디코딩.
            st.session_state["original_content"] = bytes_data.decode('utf-8', errors='ignore')
    
    content = st.session_state["original_content"]
    st.info(f"File loaded. Encoding: {st.session_state.get('encoding', 'unknown')}")

    # --- 4. UI 섹션 렌더링 및 이벤트 처리 ---
    # 각 UI 섹션을 별도의 함수로 분리하여 main 함수의 가독성 확보.
    render_context_analysis_section(settings)
    
    # "번역 시작" 버튼이 눌리면, run_translation 함수 실행.
    if st.button("Start Translation Process", type="primary"):
        run_translation(content, settings)

    # 번역이 완료되어 '금고'에 최종 결과물이 있을 경우에만 결과 및 수리 섹션을 보여줌.
    if st.session_state.get("final_srt_content"):
        render_results_and_repair(content, settings)

def handle_check_models(api_key):
    """'모델 조회' 버튼 클릭 이벤트를 처리하는 함수."""
    with st.spinner("Checking available models..."): # 사용자에게 작업 진행 중임을 알리는 스피너 표시.
        try:
            genai.configure(api_key=api_key)
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            st.session_state["fetched_models"] = models
            st.success(f"Found {len(models)} models!")
            time.sleep(1) # 사용자가 성공 메시지를 인지할 수 있도록 1초 대기.
            st.rerun() # 모델 목록을 사이드바 드롭다운에 즉시 반영하기 위해 UI를 강제 새로고침.
        except Exception as e:
            st.error(f"Error checking models: {e}")

def render_context_analysis_section(settings):
    """컨텍스트 분석(Step 1) UI 섹션을 렌더링하는 함수."""
    st.divider()
    st.subheader("🕵️ Step 1: Context Analysis (Optional)")
    col_a1, col_a2 = st.columns([1, 4]) # 버튼과 텍스트 영역의 비율을 1:4로 조절.
    if col_a1.button("🧠 Analyze Context"):
        with st.spinner("Analyzing..."):
            model = genai.GenerativeModel(settings["selected_model"])
            # core 모드의 분석 함수를 호출하여 결과를 세션 상태에 저장.
            st.session_state["context_guide"] = core.analyze_context(model, st.session_state["original_content"], settings["src_lang"], settings["tgt_lang"])
        st.rerun() # 분석 결과를 text_area에 즉시 표시하기 위해 새로고침.
    
    # 사용자가 AI의 분석 결과를 직접 수정할 수 있도록 text_area 제공하고, 수정한 내용을 다시 세션 상태에 저장.
    st.session_state["context_guide"] = col_a2.text_area("Context Guide:", st.session_state["context_guide"], height=150)

def run_translation(content, settings):
    """번역 전체 프로세스를 시작하고 실행하는 메인 워크플로우 함수."""
    # [1. 초기화]
    st.session_state["is_running"] = True # 작업 시작 플래그를 ON으로 설정.
    parsed = core.parse_srt(content)
    if not parsed: # 파싱 실패 시, 에러 메시지 표시 후 작업 중단.
        st.error("SRT parsing failed.")
        st.session_state["is_running"] = False
        return

    # 파싱 및 청킹 결과를 세션 상태에 저장.
    st.session_state.update({
        "parsed_srt": parsed,
        "chunks": core.chunk_text(parsed, settings["chunk_size"]),
    })
    
    total = len(st.session_state["chunks"])
    # 이전 작업의 결과가 남아있지 않도록 모든 결과 관련 상태를 깨끗하게 초기화.
    st.session_state.update({
        "results": [None] * total, "debugs": [None] * total,
        "chunk_states": [{'status': 'WAITING', 'duration': 0} for _ in range(total)]
    })

    # [2. 실시간 UI 준비]
    # st.empty()로 빈 공간(placeholder)을 만들어두면, 나중에 이 공간의 내용만 계속 덮어쓰며 업데이트 가능.
    timer_ph, grid_ph, status_ph = st.empty(), st.empty(), st.empty()
    model = genai.GenerativeModel(settings["selected_model"])
    start_global = time.time()
    
    # [3. 메인 번역 루프]
    # 컨베이어 벨트 시작. 청크 하나씩 순회하며 번역.
    for i, chunk in enumerate(st.session_state["chunks"]):
        # 매 루프 시작 시, '긴급 정지' 신호가 왔는지 확인.
        if not st.session_state["is_running"]:
            status_ph.warning(f"Stopped at Chunk {i}.")
            break
        
        # [UI 업데이트] 현재 청크를 '처리 중' 상태로 변경하고, 그리드와 상태 메시지를 다시 그림.
        st.session_state["chunk_states"][i]['status'] = 'RUNNING'
        with grid_ph.container(): ui.render_grid(st.session_state["chunk_states"])
        status_ph.info(f"⚡ Processing Chunk {i+1}/{total}...")
        
        # 타이머/ETA 계산 및 표시.
        elapsed = time.time() - start_global
        avg_time = elapsed / (i + 1)
        eta = avg_time * (total - (i + 1))
        # ... (타이머 렌더링 로직) ...
        
        # [핵심 로직 호출]
        texts = [item['text'] for item in chunk]
        res, debug = core.translate_chunk(model, texts, settings["src_lang"], settings["tgt_lang"], 
                                         st.session_state["context_guide"], settings["enable_reasoning"])
        
        # [결과 저장]
        st.session_state["results"][i] = res
        st.session_state["debugs"][i] = debug
        st.session_state["chunk_states"][i]['status'] = 'SUCCESS' if debug['status'] == "Success" else 'ERROR'
        st.session_state["chunk_states"][i]['duration'] = debug.get('duration', 0)
        
        time.sleep(0.5) # API 속도 제한 및 과부하 방지를 위한 최소한의 예의.
    
    # [4. 마무리]
    st.session_state["is_running"] = False # 작업 종료 플래그 OFF.
    # 모든 번역 결과를 최종 SRT 문자열로 조립하여 '금고'에 저장. 다운로드 버그 해결의 핵심.
    st.session_state["final_srt_content"] = core.rebuild_srt(st.session_state["parsed_srt"], st.session_state["results"])
    st.rerun() # '처리 중' 화면에서 '결과' 화면으로 전환하기 위해 UI 새로고침.

def render_results_and_repair(content, settings):
    """번역 완료 후 결과 표시 및 수리(Repair) UI를 렌더링하는 함수."""
    st.divider()
    st.subheader("📊 Execution Overview")
    ui.render_grid(st.session_state["chunk_states"])
    
    col_l, col_r = st.columns(2)
    col_l.text_area("Original", content, height=400)
    col_r.text_area("Translated", st.session_state["final_srt_content"], height=400)
        
    # 다운로드 버튼의 데이터는 반드시 '금고'에 저장된 최종 결과물을 사용.
    st.download_button("Download Result (.srt)", st.session_state["final_srt_content"].encode('utf-8'),
                        f"translated_{st.session_state.get('uploaded_filename', 'file.srt')}", type="primary")
    
    st.divider()
    st.subheader("🛠️ Chunk Inspector")
    
    for i, debug in enumerate(st.session_state["debugs"]):
        if not debug: continue
        is_success = debug['status'] == "Success"
        # 실패한 청크는 기본적으로 메뉴를 펼쳐서 보여줌.
        with st.expander(f"{'✅' if is_success else '❌'} Chunk {i+1}", expanded=not is_success):
            # [재시도 로직]
            if st.button(f"🔄 Retry #{i+1}", key=f"retry_{i}"):
                with st.spinner("Retrying..."):
                    # 현재 사이드바에 설정된 모든 값을 사용하여 재시도.
                    model = genai.GenerativeModel(settings["selected_model"])
                    texts = [item['text'] for item in st.session_state["chunks"][i]]
                    
                    res, new_debug = core.translate_chunk(model, texts, **settings)
                    
                    # 재시도 결과를 해당 청크 인덱스에 덮어씀.
                    st.session_state["results"][i] = res
                    st.session_state["debugs"][i] = new_debug
                    st.session_state["chunk_states"][i].update({
                        'status': 'SUCCESS' if new_debug['status'] == "Success" else 'ERROR',
                        'duration': new_debug.get('duration', 0)
                    })
                    # '금고'의 내용도 새로운 결과로 업데이트.
                    st.session_state["final_srt_content"] = core.rebuild_srt(st.session_state["parsed_srt"], st.session_state["results"])
                    # UI에 변경사항을 반영하기 위해 마지막에 한 번만 새로고침.
                    st.rerun()

# --- 애플리케이션 실행 스크립트 ---
# 이 파일이 'python app.py' 명령어로 직접 실행될 때만 main() 함수를 호출한다.
# 다른 파일에서 이 파일을 'import app'으로 불러올 때는 실행되지 않는다 (파이썬의 표준 실행 방식).
if __name__ == "__main__":
    main()