import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import re
import time
import chardet
import json
import datetime

# ---------------------------------------------------------
# [Core Logic] 자막 파싱 및 처리 엔진
# ---------------------------------------------------------

def detect_encoding(file_byte):
    result = chardet.detect(file_byte)
    return result['encoding']

def parse_srt(content):
    pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n((?:.|\n)*?)(?=\n\d+\s*\n|\Z)', re.MULTILINE)
    matches = pattern.findall(content)
    
    parsed_data = []
    for match in matches:
        parsed_data.append({
            'index': match[0],
            'time': match[1],
            'text': match[2].strip()
        })
    return parsed_data

def chunk_text(parsed_data, chunk_size=1500):
    chunks = []
    current_chunk = []
    current_length = 0
    
    for item in parsed_data:
        text_len = len(item['text'])
        if current_length + text_len > chunk_size:
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0
        
        current_chunk.append(item)
        current_length += text_len
        
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def clean_json_text(text):
    try:
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx : end_idx + 1]
            return json_str
        
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("\n", 1)[0]
        return text.strip()
    except:
        return text

def analyze_context(model, full_text, src_lang, tgt_lang):
    sample_text = full_text[:3000]
    if len(full_text) > 5000:
        mid = len(full_text) // 2
        sample_text += "\n...\n" + full_text[mid:mid+2000]
    
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
    start_time = time.time()
    max_retries = 1 
    
    debug_info = {
        "input_json": "",
        "raw_response": "",
        "status": "Unknown",
        "attempts": 0,
        "duration": 0.0,
        "context_used": "None",
        "reasoning_mode": "ON" if enable_reasoning else "OFF"
    }

    indexed_input = [{"id": i, "text": t} for i, t in enumerate(text_list)]
    input_wrapper = {"items": indexed_input}
    input_json = json.dumps(input_wrapper, ensure_ascii=False)
    debug_info["input_json"] = input_json
    
    reasoning_instruction = ""
    if enable_reasoning:
        reasoning_instruction = """
        [MAX REASONING MODE: ON]
        1. Before translating, DEEPLY ANALYZE the nuances, context, and speaker's intent for every line.
        2. Consider the flow of the conversation step-by-step.
        3. Prioritize naturalness and emotional accuracy over literal translation.
        4. YOU MUST OUTPUT ONLY THE JSON.
        """
    
    context_section = ""
    if context_guide:
        debug_info["context_used"] = context_guide
        context_section = f"""
        [CONTEXT & STYLE GUIDE]
        (You must follow these rules strictly)
        {context_guide}
        --------------------------------------------------
        """
    
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
    
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    generation_config = {
        "temperature": 0.2 if enable_reasoning else 0.1,
        "response_mime_type": "application/json"
    }
    
    for attempt in range(max_retries + 1):
        debug_info["attempts"] = attempt + 1
        try:
            response = model.generate_content(
                prompt, 
                safety_settings=safety_settings,
                generation_config=generation_config
            )
            
            raw_text = response.text
            debug_info["raw_response"] = raw_text
            
            cleaned_text = clean_json_text(raw_text)
            result_json = json.loads(cleaned_text)
            
            if "translated_items" in result_json:
                items = result_json["translated_items"]
            else:
                items = list(result_json.values())[0]
            
            items.sort(key=lambda x: x.get("id", -1))
            translated_list = []
            
            for i in range(len(text_list)):
                found = False
                for item in items:
                    if item.get("id") == i:
                        translated_list.append(item.get("text", ""))
                        found = True
                        break
                if not found:
                    translated_list.append(text_list[i]) 
                    
            if len(translated_list) != len(text_list):
                raise ValueError(f"Mismatch (In: {len(text_list)}, Out: {len(translated_list)})")
            
            debug_info["status"] = "Success"
            debug_info["duration"] = round(time.time() - start_time, 2)
            return translated_list, debug_info
            
        except Exception as e:
            debug_info["status"] = f"Error: {str(e)}"
            if attempt < max_retries:
                time.sleep(1)
                continue
            else:
                debug_info["duration"] = round(time.time() - start_time, 2)
                return text_list, debug_info

def rebuild_srt(original_data, chunks_translated):
    flat_translations = [t for chunk in chunks_translated for t in chunk]
    output = []
    limit = min(len(original_data), len(flat_translations))
    for i in range(limit):
        origin = original_data[i]
        trans = flat_translations[i]
        block = f"{origin['index']}\n{origin['time']}\n{trans}\n"
        output.append(block)
    return "\n".join(output)

def render_grid(states):
    html = """
    <style>
        .grid-container { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 20px; }
        .grid-item { 
            width: 12px; height: 12px; border-radius: 2px; 
            transition: all 0.3s ease; position: relative;
        }
        .grid-item:hover { transform: scale(1.5); z-index: 10; cursor: help; border: 1px solid #fff; }
        .status-WAITING { background-color: #e5e7eb; }
        .status-RUNNING { background-color: #3b82f6; box-shadow: 0 0 5px #3b82f6; animation: pulse 1s infinite; }
        .status-SUCCESS { background-color: #22c55e; }
        .status-ERROR { background-color: #ef4444; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
    <div class="grid-container">
    """
    for i, state in enumerate(states):
        status = state['status']
        duration = state.get('duration', 0)
        tooltip = f"Chunk {i+1}: {status} ({duration}s)"
        html += f'<div class="grid-item status-{status}" title="{tooltip}"></div>'
    html += "</div>"
    return html

# ---------------------------------------------------------
# [UI] Streamlit 인터페이스
# ---------------------------------------------------------

st.set_page_config(page_title="Ray's Subtitle Translator", layout="wide")

# State Init
if "chunks" not in st.session_state: st.session_state["chunks"] = []
if "results" not in st.session_state: st.session_state["results"] = []
if "debugs" not in st.session_state: st.session_state["debugs"] = []
if "parsed_srt" not in st.session_state: st.session_state["parsed_srt"] = []
if "chunk_states" not in st.session_state: st.session_state["chunk_states"] = []
if "is_running" not in st.session_state: st.session_state["is_running"] = False
if "context_guide" not in st.session_state: st.session_state["context_guide"] = ""
if "final_srt_content" not in st.session_state: st.session_state["final_srt_content"] = "" # [FIX] 최종 결과물 저장소

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
""", unsafe_allow_html=True)

with st.sidebar:
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
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
        except Exception:
            pass

    if st.button("🔍 Check Models"):
        if not api_key:
            st.error("API Key Required")
        else:
            try:
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                st.session_state["fetched_models"] = models
                st.success(f"Found {len(models)} models!")
            except Exception as e:
                st.error(f"Error: {e}")
    
    selected_model = None
    if "fetched_models" in st.session_state and st.session_state["fetched_models"]:
        index = 0
        for i, m in enumerate(st.session_state["fetched_models"]):
            if "flash" in m or "pro" in m:
                index = i
                break
        selected_model = st.selectbox("Select Model", st.session_state["fetched_models"], index=index, format_func=lambda x: x.replace("models/", ""))
    else:
        st.selectbox("Select Model", [], disabled=True)

    st.divider()
    chunk_size = st.slider("Chunk Size", 500, 15000, 1500, 100)
    
    st.subheader("🧠 Intelligence")
    enable_reasoning = st.toggle("Enable Reasoning Bucket (Max)", value=False, help="ON: 더 깊게 생각하고 번역합니다 (속도 느림). OFF: Auto")
    
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        src_lang = st.selectbox("From", ["English", "Korean", "Japanese"])
    with col2:
        tgt_lang = st.selectbox("To", ["Korean", "English", "Japanese"])
        
    st.divider()
    if st.session_state["is_running"]:
        if st.button("🚨 STOP PROCESS", type="primary"):
            st.session_state["is_running"] = False
            st.warning("Stopping process... Please wait.")
            
    st.markdown('<div class="footer">Made by fewweekslater</div>', unsafe_allow_html=True)

st.title("🎬 Subtitle Translator (Context-Aware)")

uploaded_file = st.file_uploader("Upload Subtitle (.srt)", type=["srt"])

if uploaded_file and api_key and selected_model:
    bytes_data = uploaded_file.getvalue()
    encoding = detect_encoding(bytes_data) or 'utf-8'
    
    try:
        content = bytes_data.decode(encoding)
    except:
        content = bytes_data.decode('utf-8', errors='ignore')
    
    st.info(f"File loaded. Encoding: {encoding}")
    
    st.divider()
    st.subheader("🕵️ Step 1: Context Analysis (Optional)")
    st.markdown("작품의 분위기, 인물 관계 등을 미리 분석하여 번역 품질을 높입니다.")
    
    col_a1, col_a2 = st.columns([1, 4])
    with col_a1:
        if st.button("🧠 Analyze Context"):
            with st.spinner("Analyzing subtitle samples..."):
                model = genai.GenerativeModel(selected_model)
                analysis_result = analyze_context(model, content, src_lang, tgt_lang)
                st.session_state["context_guide"] = analysis_result
                st.success("Analysis Done!")
    
    with col_a2:
        context_guide = st.text_area("Context Guide (Edit if needed):", value=st.session_state["context_guide"], height=150)
        st.session_state["context_guide"] = context_guide

    st.divider()
    st.subheader("🚀 Step 2: Start Translation")
    
    if st.button("Start Translation Process", type="primary"):
        parsed = parse_srt(content)
        
        if not parsed:
            st.error("Parsing Failed.")
        else:
            st.session_state["is_running"] = True
            st.session_state["parsed_srt"] = parsed
            st.session_state["chunks"] = chunk_text(parsed, chunk_size=chunk_size)
            
            total = len(st.session_state["chunks"])
            st.session_state["results"] = [None] * total
            st.session_state["debugs"] = [None] * total
            st.session_state["chunk_states"] = [{'status': 'WAITING', 'duration': 0} for _ in range(total)]
            
            timer_ph = st.empty()
            grid_ph = st.empty()
            status_ph = st.empty()
            
            model = genai.GenerativeModel(selected_model)
            start_global = time.time()
            final_context = st.session_state["context_guide"]
            
            st.subheader("📝 Live Execution Log")
            live_log_container = st.container()

            for i, chunk in enumerate(st.session_state["chunks"]):
                if not st.session_state["is_running"]:
                    status_ph.warning(f"Stopped at Chunk {i}.")
                    break
                
                st.session_state["chunk_states"][i]['status'] = 'RUNNING'
                grid_ph.markdown(render_grid(st.session_state["chunk_states"]), unsafe_allow_html=True)
                status_ph.info(f"⚡ Processing Chunk {i+1}/{total}...")
                
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
                res, debug = translate_chunk(model, texts, src_lang, tgt_lang, context_guide=final_context, enable_reasoning=enable_reasoning)
                
                st.session_state["results"][i] = res
                st.session_state["debugs"][i] = debug
                
                is_success = debug['status'] == "Success"
                st.session_state["chunk_states"][i]['status'] = 'SUCCESS' if is_success else 'ERROR'
                st.session_state["chunk_states"][i]['duration'] = debug.get('duration', 0)
                
                # ... Live Log UI Update ...
                
                grid_ph.markdown(render_grid(st.session_state["chunk_states"]), unsafe_allow_html=True)
                time.sleep(0.5)
            
            # [FIX] 번역 완료 후 최종 결과물을 '금고'에 저장
            safe_results = []
            for i, res in enumerate(st.session_state["results"]):
                if res is None:
                    safe_results.append([item['text'] for item in st.session_state["chunks"][i]])
                else:
                    safe_results.append(res)
            st.session_state["final_srt_content"] = rebuild_srt(st.session_state["parsed_srt"], safe_results)

            st.session_state["is_running"] = False
            status_ph.success("Complete!")
            time.sleep(1)
            st.rerun()

if st.session_state.get("final_srt_content"): # '금고'에 내용이 있을 때만 결과 창 표시
    st.divider()
    
    st.subheader("📊 Execution Overview")
    st.markdown(render_grid(st.session_state["chunk_states"]), unsafe_allow_html=True)
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.text_area("Original", content, height=400)
    with col_r:
        # '금고'에서 직접 꺼내옴
        st.text_area("Translated", st.session_state["final_srt_content"], height=400)
        
    st.download_button(
        "Download Result (.srt)",
        st.session_state["final_srt_content"].encode('utf-8'), # '금고'에서 직접 꺼내옴
        f"translated_{uploaded_file.name}",
        "text/plain",
        type="primary"
    )
    
    st.divider()
    st.subheader("🛠️ Chunk Inspector")
    
    for i, debug in enumerate(st.session_state["debugs"]):
        if debug is None: continue
        is_success = debug['status'] == "Success"
        icon = "✅" if is_success else "❌"
        duration = debug.get('duration', 0)
        
        default_expanded = not is_success
        with st.expander(f"{icon} Chunk {i+1} ({duration}s)", expanded=default_expanded):
            c1, c2, c3 = st.columns([1, 4, 4])
            with c1:
                if st.button(f"🔄 Retry #{i+1}", key=f"retry_{i}"):
                    with st.spinner(f"Retrying Chunk {i+1}..."):
                        model = genai.GenerativeModel(selected_model)
                        chunk = st.session_state["chunks"][i]
                        texts = [item['text'] for item in chunk]
                        
                        res, new_debug = translate_chunk(model, texts, src_lang, tgt_lang, context_guide=st.session_state["context_guide"], enable_reasoning=enable_reasoning)
                        
                        st.session_state["results"][i] = res
                        st.session_state["debugs"][i] = new_debug
                        st.session_state["chunk_states"][i]['status'] = 'SUCCESS' if new_debug['status']=="Success" else 'ERROR'
                        st.session_state["chunk_states"][i]['duration'] = new_debug.get('duration', 0)
                        
                        # [FIX] 재시도 후에도 '금고' 업데이트
                        safe_results = []
                        for j, r in enumerate(st.session_state["results"]):
                            if r is None:
                                safe_results.append([item['text'] for item in st.session_state["chunks"][j]])
                            else:
                                safe_results.append(r)
                        st.session_state["final_srt_content"] = rebuild_srt(st.session_state["parsed_srt"], safe_results)

                        st.rerun()

            with c2:
                st.caption("Sent JSON")
                st.code(debug['input_json'], language='json')
            with c3:
                it1, it2 = st.tabs(["Response JSON", "Info"])
                with it1:
                    st.code(debug['raw_response'], language='json')
                with it2:
                     st.caption(f"Reasoning Mode: {debug.get('reasoning_mode', 'OFF')}")
                     st.text_area("Used Context", debug.get('context_used', ''), height=100, disabled=True, key=f"repair_context_{i}")

elif not api_key:
    st.info("👈 API Key Required.")