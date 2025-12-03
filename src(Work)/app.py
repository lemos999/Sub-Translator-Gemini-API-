# filename: app.py

# ---------------------------------------------------------
# [1. 의존성 임포트]
# 필요한 모든 라이브러리를 여기서 불러온다.
# ---------------------------------------------------------
import streamlit as st                 # 웹 UI 프레임워크. 화면을 그리고 사용자 입력을 받는다.
import google.generativeai as genai    # 구글 Gemini AI 모델을 사용하기 위한 SDK.
from google.generativeai.types import HarmCategory, HarmBlockThreshold # AI의 유해성 콘텐츠 필터링 설정을 제어하기 위함.
import re                              # 정규 표현식 라이브러리. SRT 파일의 복잡한 텍스트 구조를 파싱하는 데 사용된다.
import time                            # 시간 관련 함수. API 호출 사이에 딜레이를 주거나, 작업 소요 시간을 측정한다.
import chardet                         # 파일의 문자 인코딩(예: UTF-8, CP949)을 자동으로 감지하는 라이브러리. 한글 깨짐 방지에 필수.
import json                            # JSON 데이터 형식을 다루기 위한 표준 라이브러리. AI와의 통신 프로토콜에 사용된다.
import datetime                        # 날짜와 시간 형식을 다루기 위함. ETA(예상 종료 시간) 표시에 사용된다.


# ---------------------------------------------------------
# [2. 핵심 로직 함수]
# 자막 번역 작업의 실제 두뇌와 손발이 되는 함수들.
# ---------------------------------------------------------

def detect_encoding(file_byte):
    """
    파일의 인코딩을 자동으로 감지한다.
    사용자가 어떤 형식의 SRT 파일을 올리든 (Windows에서 만든 CP949, Mac/Linux의 UTF-8 등)
    한글이나 특수문자가 깨지지 않도록 방지하는 중요한 함수.
    
    Args:
        file_byte (bytes): 파일의 원본 바이트 데이터.
    
    Returns:
        str: 감지된 인코딩 이름 (예: 'utf-8').
    """
    # chardet 라이브러리를 사용해 바이트 데이터를 분석.
    result = chardet.detect(file_byte)
    # 분석 결과에서 'encoding' 키 값만 반환.
    return result['encoding']

def parse_srt(content):
    """
    SRT 파일의 전체 텍스트를 입력받아,
    [인덱스, 타임코드, 텍스트] 구조의 딕셔너리 리스트로 분해(파싱)한다.
    이 함수 덕분에 메타데이터(시간)와 데이터(텍스트)를 분리할 수 있다.
    
    Args:
        content (str): SRT 파일의 전체 문자열 내용.
    
    Returns:
        list: 각 자막 블록이 딕셔너리로 변환된 리스트.
    """
    # 정규 표현식을 사용하여 SRT의 반복적인 구조를 찾아낸다.
    # (\d+): 자막 인덱스 (숫자 1개 이상)
    # \s*\n: 공백(0개 이상) 후 줄바꿈
    # (\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}): '시:분:초,밀리초 --> 시:분:초,밀리초' 형식의 타임코드
    # \s*\n: 공백 후 줄바꿈
    # ((?:.|\n)*?): 자막 텍스트. 모든 문자(.) 또는 줄바꿈(\n)이 포함될 수 있으며, 여러 줄일 수 있다.
    # (?=\n\d+\s*\n|\Z): 다음 자막 블록(줄바꿈+숫자+줄바꿈)이 나오기 직전까지 또는 파일의 끝(\Z)까지를 하나의 텍스트로 본다.
    pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n((?:.|\n)*?)(?=\n\d+\s*\n|\Z)', re.MULTILINE)
    # 정규 표현식에 맞는 모든 부분을 찾아 리스트로 반환.
    matches = pattern.findall(content)
    
    parsed_data = []
    # 찾은 각 블록을 순회하며 딕셔너리 형태로 가공.
    for match in matches:
        parsed_data.append({
            'index': match[0],         # 첫 번째 그룹: 인덱스
            'time': match[1],          # 두 번째 그룹: 타임코드
            'text': match[2].strip()   # 세 번째 그룹: 텍스트 (앞뒤 공백 제거)
        })
    return parsed_data

def chunk_text(parsed_data, chunk_size=1500):
    """
    파싱된 자막 데이터 리스트를 받아, API가 한 번에 처리할 수 있는
    일정한 크기(chunk_size)의 묶음(청크)으로 나눈다.
    
    Args:
        parsed_data (list): parse_srt 함수가 반환한 딕셔너리 리스트.
        chunk_size (int): 하나의 청크에 포함될 최대 글자 수.
    
    Returns:
        list: 딕셔너리들이 다시 리스트로 묶인 2차원 리스트 (청크의 리스트).
    """
    chunks = []
    current_chunk = []
    current_length = 0
    
    # 모든 자막 데이터를 순회.
    for item in parsed_data:
        text_len = len(item['text'])
        # 현재 청크에 이번 텍스트를 더하면 최대 크기를 초과하는지 확인.
        if current_length + text_len > chunk_size:
            # 초과하면, 지금까지의 청크를 최종 청크 리스트에 추가.
            chunks.append(current_chunk)
            # 현재 청크와 길이를 초기화.
            current_chunk = []
            current_length = 0
        
        # 현재 청크에 자막 데이터를 추가하고, 길이를 누적.
        current_chunk.append(item)
        current_length += text_len
        
    # 마지막에 남은 청크가 있으면 그것도 최종 리스트에 추가.
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks

def clean_json_text(text):
    """
    AI가 반환한 텍스트에서 순수한 JSON 부분만 외과적으로 추출한다.
    AI가 "번역 결과입니다: { ... }" 와 같이 불필요한 사족을 붙이거나,
    마크다운 코드 블록(```json ... ```)으로 감싸는 경우에 대한 방어 로직.
    
    Args:
        text (str): AI가 반환한 원본 응답 문자열.
        
    Returns:
        str: JSON 객체로 추정되는 부분만 남긴 문자열.
    """
    try:
        # 1. 가장 바깥쪽의 '{' 와 '}'를 찾아 그 사이의 모든 것을 추출. 가장 확실한 방법.
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx : end_idx + 1]
            return json_str
        
        # 2. 위 방법이 실패하면, 마크다운 코드 블록을 제거하는 예전 방식 시도.
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("\n", 1)[0]
        return text.strip()
    except:
        # 예외 발생 시, 그냥 원본 텍스트 반환 (후속 로직에서 에러 처리).
        return text

def analyze_context(model, full_text, src_lang, tgt_lang):
    """
    전체 자막의 일부를 샘플링하여 AI에게 보내고,
    작품의 장르, 톤, 인물 관계, 핵심 용어 등을 분석한 '컨텍스트 가이드'를 받아온다.
    
    Args:
        model: 사용할 Gemini AI 모델 객체.
        full_text (str): 자막 전체 텍스트.
        src_lang (str): 소스 언어.
        tgt_lang (str): 타겟 언어.
    
    Returns:
        str: AI가 작성한 컨텍스트 가이드 텍스트.
    """
    # 토큰 비용과 시간을 아끼기 위해 전체가 아닌 일부만 샘플링.
    # 가장 정보가 밀집된 초반 3000자와, 분위기 파악을 위한 중간 2000자를 조합.
    sample_text = full_text[:3000]
    if len(full_text) > 5000:
        mid = len(full_text) // 2
        sample_text += "\n...\n" + full_text[mid:mid+2000]
    
    # AI에게 역할을 부여하고, 무엇을 분석해야 하는지 명확하게 지시하는 프롬프트.
    # 특히 "일반 단어는 제외하라"고 명시하여 결과물의 품질을 높임.
    prompt = f"""
    Analyze the following subtitle sample to prepare for translation from {src_lang} to {tgt_lang}.
    
    [Subtitle Sample]
    {sample_text}
    
    [Task]
    Provide a "System Context Guide" for the translator AI.
    
    [Requirements]
    1. **Genre & Tone**: Define the atmosphere.
    2. **Character & Relationships**: Identify key characters. Who speaks formally/informally to whom?
    3. **Consistency Rules (Glossary)**:
       - List ONLY technical terms, proper nouns, or ambiguous words that need consistency.
       - Do NOT list common words (e.g., "farmer", "school") unless they have a special hidden meaning.
       - Keep it minimal and strictly relevant.
    
    [Output Format]
    Write a concise guide in {tgt_lang}.
    """
    
    response = model.generate_content(prompt)
    return response.text.strip()

def translate_chunk(model, text_list, src_lang, tgt_lang, context_guide="", enable_reasoning=False):
    """
    하나의 텍스트 청크를 받아 AI에게 번역을 요청하고, 그 결과를 반환하는 핵심 함수.
    ID 앵커링, JSON 강제 모드, 자동 재시도, 컨텍스트 주입, 추론 모드 등 모든 핵심 기술이 집약되어 있다.
    
    Args:
        model: 사용할 Gemini AI 모델 객체.
        text_list (list): 번역할 문자열들의 리스트.
        src_lang (str): 소스 언어.
        tgt_lang (str): 타겟 언어.
        context_guide (str, optional): 사전 분석된 컨텍스트 가이드.
        enable_reasoning (bool, optional): 추론 버킷(고품질) 모드 활성화 여부.
    
    Returns:
        tuple: (번역된 텍스트 리스트, 디버그 정보 딕셔너리)
    """
    start_time = time.time()  # 성능 측정을 위해 시작 시간 기록.
    max_retries = 1           # 네트워크 등 일시적 오류에 대비한 최대 재시도 횟수.
    
    # 디버깅 및 상태 로깅을 위한 정보를 담을 딕셔너리.
    debug_info = {
        "input_json": "", "raw_response": "", "status": "Unknown", "attempts": 0,
        "duration": 0.0, "context_used": "None", "reasoning_mode": "ON" if enable_reasoning else "OFF"
    }

    # [ID 앵커링] 단순 텍스트 리스트를 [{"id": 0, "text": "..."}, ...] 구조로 변환.
    indexed_input = [{"id": i, "text": t} for i, t in enumerate(text_list)]
    input_wrapper = {"items": indexed_input}
    input_json = json.dumps(input_wrapper, ensure_ascii=False)
    debug_info["input_json"] = input_json # 디버깅을 위해 보낸 JSON 원본 저장.
    
    # [추론 버킷] 추론 모드가 켜졌을 경우, 프롬프트에 추가 지시 사항 삽입.
    reasoning_instruction = ""
    if enable_reasoning:
        reasoning_instruction = """
        [MAX REASONING MODE: ON]
        1. Before translating, DEEPLY ANALYZE the nuances, context, and speaker's intent for every line.
        2. Consider the flow of the conversation step-by-step.
        3. Prioritize naturalness and emotional accuracy over literal translation.
        4. YOU MUST OUTPUT ONLY THE JSON.
        """
    
    # [컨텍스트 주입] 컨텍스트 가이드가 있을 경우, 프롬프트에 추가.
    context_section = ""
    if context_guide:
        debug_info["context_used"] = context_guide
        context_section = f"""
        [CONTEXT & STYLE GUIDE]
        (You must follow these rules strictly)
        {context_guide}
        --------------------------------------------------
        """
    
    # 최종 프롬프트 조립.
    prompt = f"""
    You are a professional subtitle translator.
    Translate the "text" field in the JSON objects from {src_lang} to {tgt_lang}.
    {reasoning_instruction}
    {context_section}
    [INPUT JSON]
    {input_json}
    [CRITICAL RULES]
    1. Output MUST be a valid JSON object with a key "translated_items".
    2. "translated_items" is a list of objects: {{"id": integer, "text": "translated_string"}}.
    3. You MUST preserve the "id" exactly as is.
    4. Do NOT merge or split lines. One ID = One Line.
    [OUTPUT SCHEMA]
    {{ "translated_items": [ {{"id": 0, "text": "..."}}, ... ] }}
    """
    
    # AI의 유해성 콘텐츠 필터를 모두 비활성화. (소설/드라마의 폭력적이거나 선정적인 대사 차단 방지)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    # AI 모델의 동작을 제어하는 설정.
    generation_config = {
        "temperature": 0.2 if enable_reasoning else 0.1, # 추론 모드일 때 창의성을 약간 높여 더 나은 표현을 찾도록 함.
        "response_mime_type": "application/json"        # [JSON 강제 모드] API가 반드시 유효한 JSON만 반환하도록 강제.
    }
    
    # [자동 재시도 로직]
    for attempt in range(max_retries + 1):
        debug_info["attempts"] = attempt + 1
        try:
            # AI에게 번역 요청.
            response = model.generate_content(prompt, safety_settings=safety_settings, generation_config=generation_config)
            
            raw_text = response.text
            debug_info["raw_response"] = raw_text # 받은 응답 원본 저장.
            
            # 응답 텍스트에서 순수 JSON만 추출.
            cleaned_text = clean_json_text(raw_text)
            result_json = json.loads(cleaned_text)
            
            # 약속된 키("translated_items")로 데이터 추출.
            if "translated_items" in result_json:
                items = result_json["translated_items"]
            else: # 혹시 AI가 다른 키를 사용했을 경우를 대비한 방어 코드.
                items = list(result_json.values())[0]
            
            # AI가 응답 순서를 뒤섞었을 수 있으므로, ID를 기준으로 다시 정렬.
            items.sort(key=lambda x: x.get("id", -1))
            
            # ID를 기준으로 원본 순서에 맞게 번역된 텍스트만 추출하여 최종 리스트 생성.
            translated_list = []
            for i in range(len(text_list)):
                found = False
                for item in items:
                    if item.get("id") == i:
                        translated_list.append(item.get("text", ""))
                        found = True
                        break
                if not found: # 만약 AI가 특정 ID를 누락했다면, 원본 텍스트로 대체 (싱크 깨짐 방지).
                    translated_list.append(text_list[i]) 
                    
            # 최종적으로 입력과 출력의 개수가 같은지 검증.
            if len(translated_list) != len(text_list):
                raise ValueError(f"Mismatch (In: {len(text_list)}, Out: {len(translated_list)})")
            
            # 모든 과정이 성공했을 경우.
            debug_info["status"] = "Success"
            debug_info["duration"] = round(time.time() - start_time, 2)
            return translated_list, debug_info # 성공 결과 반환.
            
        except Exception as e:
            # 에러 발생 시 디버그 정보 기록.
            debug_info["status"] = f"Error: {str(e)}"
            if attempt < max_retries:
                time.sleep(1) # 재시도 전 1초 대기.
                continue      # 루프의 다음 시도로 넘어감.
            else:
                # 최종 실패 시, 원본 텍스트 리스트와 디버그 정보 반환.
                debug_info["duration"] = round(time.time() - start_time, 2)
                return text_list, debug_info

def rebuild_srt(original_data, chunks_translated):
    """
    번역된 텍스트 청크 리스트와 원본 파싱 데이터를 받아,
    하나의 완전한 SRT 파일 내용으로 재조립한다.
    
    Args:
        original_data (list): parse_srt가 생성한 원본 구조 리스트.
        chunks_translated (list): 번역된 텍스트들로 구성된 2차원 리스트.
    
    Returns:
        str: 최종 SRT 파일 내용 문자열.
    """
    # 2차원 리스트를 1차원 리스트로 평탄화.
    flat_translations = [t for chunk in chunks_translated for t in chunk]
    
    output = []
    # 원본 데이터와 번역 데이터의 개수가 다를 경우를 대비해, 더 적은 쪽에 맞춰 안전하게 순회.
    limit = min(len(original_data), len(flat_translations))
    for i in range(limit):
        origin = original_data[i]
        trans = flat_translations[i]
        # 원본의 [인덱스, 타임코드]와 번역된 [텍스트]를 합쳐 SRT 블록 생성.
        block = f"{origin['index']}\n{origin['time']}\n{trans}\n"
        output.append(block)
    
    # 모든 블록을 줄바꿈으로 합쳐 최종 파일 내용 생성.
    return "\n".join(output)

def render_grid(states):
    """
    청크들의 상태 리스트를 받아, 시각적인 상태 그리드 HTML을 생성한다.
    
    Args:
        states (list): 각 청크의 상태({'status': '...', 'duration': ...})를 담은 딕셔너리 리스트.
    
    Returns:
        str: 그리드를 표시하기 위한 HTML/CSS 코드.
    """
    # CSS 스타일 정의: 그리드 레이아웃, 각 상태별 색상, 호버 효과, 애니메이션 등.
    html = """
    <style>
        .grid-container { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 20px; }
        .grid-item { width: 12px; height: 12px; border-radius: 2px; transition: all 0.3s ease; position: relative; }
        .grid-item:hover { transform: scale(1.5); z-index: 10; cursor: help; border: 1px solid #fff; }
        .status-WAITING { background-color: #e5e7eb; }
        .status-RUNNING { background-color: #3b82f6; box-shadow: 0 0 5px #3b82f6; animation: pulse 1s infinite; }
        .status-SUCCESS { background-color: #22c55e; }
        .status-ERROR { background-color: #ef4444; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
    <div class="grid-container">
    """
    # 각 청크 상태에 따라 CSS 클래스를 적용하고, 마우스를 올리면 상세 정보가 보이도록 툴팁(title 속성) 추가.
    for i, state in enumerate(states):
        status = state['status']
        duration = state.get('duration', 0)
        tooltip = f"Chunk {i+1}: {status} ({duration}s)"
        html += f'<div class="grid-item status-{status}" title="{tooltip}"></div>'
    html += "</div>"
    return html


# ---------------------------------------------------------
# [3. UI 렌더링 및 메인 로직]
# Streamlit을 사용하여 화면을 구성하고, 사용자 입력에 따라 함수를 호출한다.
# ---------------------------------------------------------

# 페이지 기본 설정: 제목, 레이아웃 등.
st.set_page_config(page_title="Ray's Subtitle Translator", layout="wide")

# [세션 상태(Session State) 초기화]
# Streamlit은 버튼을 누르거나 상호작용할 때마다 스크립트를 재실행하는데,
# 이 때 변수들이 날아가지 않도록 데이터를 보관하는 '메모리' 역할을 한다.
if "chunks" not in st.session_state: st.session_state["chunks"] = []
if "results" not in st.session_state: st.session_state["results"] = []
if "debugs" not in st.session_state: st.session_state["debugs"] = []
if "parsed_srt" not in st.session_state: st.session_state["parsed_srt"] = []
if "chunk_states" not in st.session_state: st.session_state["chunk_states"] = []
if "is_running" not in st.session_state: st.session_state["is_running"] = False
if "context_guide" not in st.session_state: st.session_state["context_guide"] = ""
if "final_srt_content" not in st.session_state: st.session_state["final_srt_content"] = "" # 최종 번역 결과물을 보관할 금고.

# [CSS 주입]
# Streamlit의 기본 스타일을 오버라이드하여, 더 미려한 UI를 만들기 위한 커스텀 CSS.
st.markdown("""
<style>
    [data-testid="stSidebar"] { min-width: 350px; max-width: 500px; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .metric-box { border: 1px solid #ddd; padding: 10px; border-radius: 8px; text-align: center; background: #fdfdfd; }
    .metric-val { font-size: 1.5em; font-weight: bold; color: #333; }
    .metric-label { font-size: 0.9em; color: #666; }
    .github-link { text-decoration: none; color: #fafafa; }
    .github-icon svg { width: 20px; height: 20px; fill: currentColor; margin-right: 8px; vertical-align: middle; transition: color 0.2s; }
    .github-link:hover { color: #3b82f6; }
    .footer { font-size: 0.8em; color: #aaa; text-align: center; }
</style>
""", unsafe_allow_html=True) # unsafe_allow_html=True는 HTML/CSS를 직접 렌더링하기 위해 필수.

# [사이드바 UI 구성]
with st.sidebar:
    # 깃허브 링크 (SVG 아이콘 포함)
    st.markdown("""
    <a href="https://github.com/lemos999" target="_blank" class="github-link">
        <span class="github-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.07-.55-.17-.55-.38 0-.19.01-.82.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21-.15.46-.55.38A8.013 8.013 0 0 1 0 8c0-4.42 3.58-8 8-8Z"></path></svg>
        </span>
        lemos999's GitHub
    </a>
    """, unsafe_allow_html=True)
    
    st.header("⚙️ Settings")
    api_key = st.text_input("Google API Key", type="password")
    
    # API 키가 입력되면, 즉시 SDK 설정.
    if api_key:
        try: genai.configure(api_key=api_key)
        except Exception: pass

    # 모델 목록 조회 버튼.
    if st.button("🔍 Check Models"):
        if not api_key: st.error("API Key Required")
        else:
            try:
                # 'generateContent'를 지원하는 모델만 필터링하여 가져옴.
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                st.session_state["fetched_models"] = models
                st.success(f"Found {len(models)} models!")
            except Exception as e:
                st.error(f"Error: {e}")
    
    selected_model = None
    if "fetched_models" in st.session_state and st.session_state["fetched_models"]:
        # 리스트에 모델이 있으면, 드롭다운 메뉴를 보여줌.
        index = 0
        for i, m in enumerate(st.session_state["fetched_models"]):
            if "flash" in m or "pro" in m: # 'flash'나 'pro' 모델을 기본 선택으로 유도.
                index = i
                break
        selected_model = st.selectbox("Select Model", st.session_state["fetched_models"], index=index,
                                      format_func=lambda x: x.replace("models/", "")) # UI에는 'models/' 접두사 빼고 보여줌.
    else:
        st.selectbox("Select Model", [], disabled=True) # 모델 없으면 비활성화.

    st.divider()
    chunk_size = st.slider("Chunk Size", 500, 15000, 1500, 100) # 청크 크기 조절 슬라이더.
    
    st.subheader("🧠 Intelligence")
    enable_reasoning = st.toggle("Enable Reasoning Bucket (Max)", value=False) # 추론 모드 토글.
    
    st.divider()
    col1, col2 = st.columns(2) # 언어 선택을 좌우로 배치하기 위한 컬럼.
    with col1: src_lang = st.selectbox("From", ["English", "Korean", "Japanese"])
    with col2: tgt_lang = st.selectbox("To", ["Korean", "English", "Japanese"])
        
    st.divider()
    # [긴급 정지] is_running 상태일 때만 버튼이 보임.
    if st.session_state["is_running"]:
        if st.button("🚨 STOP PROCESS", type="primary"):
            st.session_state["is_running"] = False # 플래그를 False로 바꿔서 메인 루프가 멈추도록 함.
            st.warning("Stopping process... Please wait.")
            
    # 제작자 크레딧.
    st.markdown('<div class="footer">Made by fewweekslater</div>', unsafe_allow_html=True)

# [메인 페이지 UI 구성]
st.title("🎬 Subtitle Translator (Context-Aware)")

uploaded_file = st.file_uploader("Upload Subtitle (.srt)", type=["srt"])

# 모든 조건(파일, API키, 모델)이 충족되었을 때만 아래 로직 실행.
if uploaded_file and api_key and selected_model:
    bytes_data = uploaded_file.getvalue()
    encoding = detect_encoding(bytes_data) or 'utf-8' # 인코딩 감지 실패 시 utf-8로 강제.
    
    try: content = bytes_data.decode(encoding)
    except: content = bytes_data.decode('utf-8', errors='ignore') # 그래도 실패하면 손상된 문자는 무시하고 디코딩.
    
    st.info(f"File loaded. Encoding: {encoding}")
    
    st.divider()
    st.subheader("🕵️ Step 1: Context Analysis (Optional)")
    
    col_a1, col_a2 = st.columns([1, 4])
    with col_a1:
        if st.button("🧠 Analyze Context"):
            with st.spinner("Analyzing..."):
                model = genai.GenerativeModel(selected_model)
                analysis_result = analyze_context(model, content, src_lang, tgt_lang)
                st.session_state["context_guide"] = analysis_result
                st.success("Analysis Done!")
    
    with col_a2:
        # 사용자가 AI의 분석 결과를 직접 수정할 수 있도록 text_area 제공.
        context_guide = st.text_area("Context Guide (Edit if needed):", value=st.session_state["context_guide"], height=150)
        st.session_state["context_guide"] = context_guide # 수정된 내용을 세션 상태에 즉시 반영.

    st.divider()
    st.subheader("🚀 Step 2: Start Translation")
    
    # [번역 시작 버튼]
    if st.button("Start Translation Process", type="primary"):
        parsed = parse_srt(content)
        if not parsed: st.error("Parsing Failed.")
        else:
            st.session_state["is_running"] = True # 작업 시작 플래그 ON.
            st.session_state["parsed_srt"] = parsed
            st.session_state["chunks"] = chunk_text(parsed, chunk_size=chunk_size)
            
            total = len(st.session_state["chunks"])
            # 모든 상태 리스트들을 청크 개수에 맞게 초기화.
            st.session_state["results"] = [None] * total
            st.session_state["debugs"] = [None] * total
            st.session_state["chunk_states"] = [{'status': 'WAITING', 'duration': 0} for _ in range(total)]
            
            # 실시간 업데이트를 위한 빈 공간(placeholder) 확보.
            timer_ph = st.empty()
            grid_ph = st.empty()
            status_ph = st.empty()
            
            model = genai.GenerativeModel(selected_model)
            start_global = time.time()
            final_context = st.session_state["context_guide"]
            
            st.subheader("📝 Live Execution Log")
            live_log_container = st.container()

            # [메인 번역 루프]
            for i, chunk in enumerate(st.session_state["chunks"]):
                # 긴급 정지 버튼이 눌렸는지 매번 확인.
                if not st.session_state["is_running"]:
                    status_ph.warning(f"Stopped at Chunk {i}.")
                    break
                
                # 대시보드 UI 업데이트 (처리중 상태).
                st.session_state["chunk_states"][i]['status'] = 'RUNNING'
                grid_ph.markdown(render_grid(st.session_state["chunk_states"]), unsafe_allow_html=True)
                status_ph.info(f"⚡ Processing Chunk {i+1}/{total}...")
                
                # 타이머/ETA 계산 및 표시.
                elapsed = time.time() - start_global
                avg_time = elapsed / (i if i > 0 else 1)
                eta = avg_time * (total - i)
                timer_ph.markdown(f"""
                <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                    <div class="metric-box" style="flex:1"><div class="metric-label">Elapsed</div><div class="metric-val">{datetime.timedelta(seconds=int(elapsed))}</div></div>
                    <div class="metric-box" style="flex:1"><div class="metric-label">Chunk Avg</div><div class="metric-val">{avg_time:.1f}s</div></div>
                    <div class="metric-box" style="flex:1"><div class="metric-label">ETA</div><div class="metric-val">{datetime.timedelta(seconds=int(eta))}</div></div>
                </div>
                """, unsafe_allow_html=True)
                
                texts = [item['text'] for item in chunk]
                # 핵심 번역 함수 호출.
                res, debug = translate_chunk(model, texts, src_lang, tgt_lang, context_guide=final_context, enable_reasoning=enable_reasoning)
                
                # 결과 저장.
                st.session_state["results"][i] = res
                st.session_state["debugs"][i] = debug
                
                # 대시보드 UI 업데이트 (성공/실패 상태).
                is_success = debug['status'] == "Success"
                st.session_state["chunk_states"][i]['status'] = 'SUCCESS' if is_success else 'ERROR'
                st.session_state["chunk_states"][i]['duration'] = debug.get('duration', 0)
                
                # ... 라이브 로그 UI 업데이트 생략 (코드가 너무 길어져서) ...
                
                grid_ph.markdown(render_grid(st.session_state["chunk_states"]), unsafe_allow_html=True)
                time.sleep(0.5) # API 과부하 방지를 위한 약간의 딜레이.
            
            # [최종 결과물 저장]
            # 루프가 끝나면, 현재까지의 결과로 최종 SRT 문자열을 만들어 '금고'에 저장.
            safe_results = []
            for i, res in enumerate(st.session_state["results"]):
                if res is None: safe_results.append([item['text'] for item in st.session_state["chunks"][i]])
                else: safe_results.append(res)
            st.session_state["final_srt_content"] = rebuild_srt(st.session_state["parsed_srt"], safe_results)

            st.session_state["is_running"] = False # 작업 종료 플래그 OFF.
            status_ph.success("Complete!")
            time.sleep(1)
            st.rerun() # UI를 '처리중' 화면에서 '결과' 화면으로 전환하기 위해 스크립트 재실행.

# [결과 및 수리(Repair) 화면]
# 최종 결과물이 '금고'에 저장되어 있을 때만 이 부분을 그림.
if st.session_state.get("final_srt_content"):
    st.divider()
    
    st.subheader("📊 Execution Overview")
    st.markdown(render_grid(st.session_state["chunk_states"]), unsafe_allow_html=True)
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.text_area("Original", content, height=400)
    with col_r:
        # 화면에 표시되는 텍스트는 '금고'에서 직접 꺼내옴.
        st.text_area("Translated", st.session_state["final_srt_content"], height=400)
        
    # 다운로드 버튼도 '금고'에 저장된 최종 결과물을 데이터로 사용.
    st.download_button(
        "Download Result (.srt)",
        st.session_state["final_srt_content"].encode('utf-8'),
        f"translated_{uploaded_file.name}",
        "text/plain",
        type="primary"
    )
    
    st.divider()
    st.subheader("🛠️ Chunk Inspector")
    
    # [수동 재시도 로직]
    for i, debug in enumerate(st.session_state["debugs"]):
        if debug is None: continue
        is_success = debug['status'] == "Success"
        icon = "✅" if is_success else "❌"
        duration = debug.get('duration', 0)
        
        default_expanded = not is_success # 실패한 청크는 기본적으로 펼쳐서 보여줌.
        with st.expander(f"{icon} Chunk {i+1} ({duration}s)", expanded=default_expanded):
            c1, c2, c3 = st.columns([1, 4, 4])
            with c1:
                # 각 버튼에 고유한 key를 부여하여 서로 구분.
                if st.button(f"🔄 Retry #{i+1}", key=f"retry_{i}"):
                    # st.spinner: '처리중'이라는 시각적 피드백을 주기 위함.
                    with st.spinner(f"Retrying Chunk {i+1}..."):
                        model = genai.GenerativeModel(selected_model)
                        chunk = st.session_state["chunks"][i]
                        texts = [item['text'] for item in chunk]
                        
                        # 재시도 실행.
                        res, new_debug = translate_chunk(model, texts, src_lang, tgt_lang, context_guide=st.session_state["context_guide"], enable_reasoning=enable_reasoning)
                        
                        # 새로운 결과로 세션 상태 업데이트.
                        st.session_state["results"][i] = res
                        st.session_state["debugs"][i] = new_debug
                        st.session_state["chunk_states"][i]['status'] = 'SUCCESS' if new_debug['status']=="Success" else 'ERROR'
                        st.session_state["chunk_states"][i]['duration'] = new_debug.get('duration', 0)
                        
                        # 재시도 후에도 '금고'를 최신 상태로 업데이트.
                        safe_results = []
                        for j, r in enumerate(st.session_state["results"]):
                            if r is None: safe_results.append([item['text'] for item in st.session_state["chunks"][j]])
                            else: safe_results.append(r)
                        st.session_state["final_srt_content"] = rebuild_srt(st.session_state["parsed_srt"], safe_results)

                        # 모든 업데이트가 끝나고 마지막에 한 번만 UI 새로고침.
                        st.rerun()

            with c2:
                st.caption("Sent JSON")
                st.code(debug['input_json'], language='json')
            with c3:
                it1, it2 = st.tabs(["Response JSON", "Info"])
                with it1: st.code(debug['raw_response'], language='json')
                with it2:
                     st.caption(f"Reasoning Mode: {debug.get('reasoning_mode', 'OFF')}")
                     st.text_area("Used Context", debug.get('context_used', ''), height=100, disabled=True, key=f"repair_context_{i}")

elif not api_key:
    st.info("👈 API Key Required.")