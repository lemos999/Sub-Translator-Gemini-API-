# Context-Aware Subtitle Translator

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A stateless subtitle translator powered by the Google Gemini API, meticulously engineered for perfect metadata preservation and translation.

## Key Features

*   **🖥️ Stateless & Browser-Based UI:** Built with Streamlit, the tool runs in any modern web browser, offering a clean, intuitive interface that works on any operating system.
*   **🕒 Perfect Metadata Preservation:** At its core, the translator operates on a "Conveyor Belt Architecture," which surgically separates subtitle text from its metadata (timestamps, indices). Only the text is sent for translation, ensuring that timing information remains untouched and perfectly synchronized.
*   **🔗 Robust AI Communication (ID Anchoring Protocol):** We solved the critical "Count Mismatch" problem where LLMs merge or split lines arbitrarily. Every line is anchored with a unique ID, forcing the AI to maintain a 1:1 structural correspondence between the source and translated text. This guarantees that the reassembled subtitle file is never corrupted.
*   **🧠 Context-Aware Engine (In-Progress):** The system employs a "Scout-Report-Inject" architecture to analyze the script's genre, tone, and character relationships beforehand. This generated "Context Guide" is injected into every translation request, dramatically improving consistency and tonal accuracy.
    *   **Note:** While the framework for deep context analysis is in place, achieving perfect narrative and emotional context across an entire script is an ongoing challenge and a key area for future improvement. The current implementation provides a significant quality boost but is not yet infallible.
*   **🚀 Live Execution Dashboard:** A visual grid displays the real-time status of each chunk (Waiting, Processing, Success, Error), complemented by a HUD showing elapsed time, average chunk speed, and an estimated time of completion (ETA).
*   **🔧 Advanced Control & Tuning:**
    *   **Manual Retry & Emergency Stop:** Failed chunks can be retried individually without restarting the entire process. A global stop button allows you to halt the operation at any time.
    *   **Reasoning Bucket:** A toggle to switch the AI into "Max Reasoning" mode, instructing it to perform deeper, step-by-step analysis for higher-quality translation of nuanced dialogue, at the cost of speed.
    *   **Adjustable Chunk Size:** A slider to control the amount of text sent per API call, allowing users to balance speed against stability.

## Getting Started (For Developers)

Follow these steps to run the application in your local development environment.

### Prerequisites

*   Python 3.9 or higher
*   An active Google API Key with the Gemini API enabled. You can get one from [Google AI Studio](https://aistudio.google.com/app/apikey).

### Installation & Execution

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/your-project.git
    cd your-project
    ```

2.  **(Recommended) Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required libraries:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    streamlit run app.py
    ```

5.  Your web browser will automatically open with the application running. Enter your Google API Key in the sidebar to begin.

## How It Works: The "Conveyor Belt" Architecture

The system's data flow is designed for maximum safety and efficiency, mirroring an industrial conveyor belt.

1.  **Deconstruction:** The input SRT file is precisely disassembled into two distinct components: **Metadata** (timestamps) and **Data** (dialogue text).
2.  **Refinement:** The Metadata is securely stored locally. Only the pure text data proceeds to the next stage, preventing any possibility of metadata corruption by the AI.
3.  **Batch Processing:** The text is grouped into manageable chunks according to the user-defined size. These chunks are then formatted into a strict JSON structure using the ID Anchoring protocol.
4.  **Reassembly:** Once the AI returns the translated JSON, the system validates its integrity, re-sorts it by ID, and meticulously reassembles it with the original, untouched Metadata to produce the final, perfectly synchronized subtitle file.

## Core Technology: The AI Communication Protocol

### The Breakthrough Solution: "ID Anchoring" with Forced JSON Mode

Our protocol neutralizes the LLM's tendency to alter text structure by combining a logical data structure with a strict API-level command.

1.  **ID Anchoring: Enforcing Structural Invariance**

    Instead of sending a simple list of strings, which the AI might interpret as a single, malleable block of text, we send an array of objects. Each object is "anchored" with a unique, sequential `id`.

    **Data Structure Sent to AI:**
    ```json
    [
      {"id": 0, "text": "Line 1 text."},
      {"id": 1, "text": "Line 2 text."},
      {"id": 2, "text": "Line 3 text."}
    ]
    ```

    This structure acts as a logical "shackle." The AI is instructed via the prompt to preserve the `id` for each object. This simple rule has profound implications:
    *   **Merging is impossible:** The AI cannot merge line 1 and 2 into a single translated object without either destroying an ID (`id: 1`) or creating an invalid structure.
    *   **Splitting is impossible:** The AI cannot split line 3 into two translated objects without fabricating a new ID, which violates the instruction.

    This forces a strict **1-to-1 mapping** between the input and output objects at a structural level, regardless of the text content. Even if the AI reorders the objects in its response, we can reliably sort them back into the correct sequence using the immutable IDs.

2.  **API-Level Forced JSON Mode: Guaranteeing Data Integrity**

    While ID Anchoring solves the structural mapping problem, it doesn't prevent the AI from returning a response that isn't valid JSON (e.g., by adding conversational text like `"Here is your translation: ..."`). To eliminate this, we bypass prompt-level requests entirely.

    We configure the Gemini API call to set the `response_mime_type` parameter to `application/json`. This is not a suggestion; it is a **system-level command** to the API server. It contractually binds the server to return a response that is nothing but a syntactically perfect JSON object. This completely eradicates any possibility of `JSONDecodeError` and makes the communication pipeline exceptionally robust.

## Technology Stack

*   **Core & Logic:** `Python 3.13`, `Streamlit 1.51.0`
*   **AI Engine & Communication:** `google-generativeai`, `chardet`
*   **Packaging & Deployment:** `PyInstaller 6.17.0`, `UPX 4.2.4`

---
<br>

# 컨텍스트-인식 자막 번역기

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Google Gemini API를 기반으로, 완벽한 메타데이터 보존과 번역을 위해 정밀하게 설계된 비저장식 자막 번역기입니다.

## 핵심 기능

*   **🖥️ 비저장식 & 브라우저 기반 UI:** Streamlit으로 제작되어 모든 최신 웹 브라우저에서 실행되며, 어떤 운영체제에서든 깔끔하고 직관적인 인터페이스를 제공합니다.
*   **🕒 완벽한 메타데이터 보존:** 시스템의 핵심에는 '컨베이어 벨트 아키텍처'가 있습니다. 이 구조는 자막 텍스트를 타임스탬프, 인덱스와 같은 메타데이터로부터 외과적으로 분리합니다. 오직 텍스트만 번역을 위해 전송되므로, 시간 정보는 절대 훼손되지 않고 완벽한 동기화를 유지합니다.
*   **🔗 견고한 AI 통신 (ID 앵커링 프로토콜):** LLM이 임의로 줄을 합치거나 나누는 치명적인 '개수 불일치' 문제를 해결했습니다. 모든 줄은 고유 ID로 고정되어, AI가 소스와 번역 텍스트 간의 1:1 구조적 대응을 유지하도록 강제합니다. 이는 재조립된 자막 파일이 절대 손상되지 않음을 보장합니다.
*   **🧠 컨텍스트-인식 엔진 (개발 진행 중):** 시스템은 "스카우트-리포트-주입" 아키텍처를 채택하여, 번역 전 스크립트의 장르, 톤, 인물 관계를 미리 분석합니다. 이렇게 생성된 '컨텍스트 가이드'는 모든 번역 요청에 주입되어 일관성과 톤의 정확성을 극적으로 향상시킵니다.
    *   **참고:** 심층 문맥 분석을 위한 프레임워크는 마련되었으나, 스크립트 전체에 걸쳐 완벽한 서사적, 감정적 문맥을 달성하는 것은 여전히 도전적인 과제이며 향후 개선의 핵심 영역입니다. 현재 구현은 상당한 품질 향상을 제공하지만, 아직 완벽하지는 않습니다.
*   **🚀 실시간 실행 대시보드:** 시각적 그리드가 각 청크의 상태(대기, 처리 중, 성공, 실패)를 실시간으로 표시하며, 경과 시간, 평균 청크 속도, 예상 완료 시간을 보여주는 HUD가 함께 제공됩니다.
*   **🔧 고급 제어 및 튜닝:**
    *   **수동 재시도 & 긴급 정지:** 실패한 청크는 전체 프로세스를 다시 시작할 필요 없이 개별적으로 재시도할 수 있습니다. 전역 정지 버튼으로 언제든지 작업을 중단할 수 있습니다.
    *   **추론 버킷:** AI를 '최대 추론' 모드로 전환하는 토글입니다. 속도를 희생하는 대신, 미묘한 뉘앙스의 대사를 위해 더 깊고 단계적인 분석을 수행하도록 지시하여 고품질 번역을 유도합니다.
    *   **청크 크기 조절:** API 호출당 전송되는 텍스트 양을 제어하는 슬라이더로, 사용자가 속도와 안정성 사이의 균형을 맞출 수 있습니다.

## 시작하기 (개발자용)

로컬 개발 환경에서 애플리케이션을 실행하려면 다음 단계를 따르세요.

### 사전 준비물

*   Python 3.9 이상
*   Gemini API가 활성화된 Google API 키. [Google AI Studio](https://aistudio.google.com/app/apikey)에서 발급받을 수 있습니다.

### 설치 및 실행

1.  **리포지토리 클론:**
    ```bash
    git clone https://github.com/your-repo/your-project.git
    cd your-project
    ```

2.  **(권장) 가상환경 생성 및 활성화:**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    
    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **필요 라이브러리 설치:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **애플리케이션 실행:**
    ```bash
    streamlit run app.py
    ```

5.  웹 브라우저가 자동으로 열리며 애플리케이션이 실행됩니다. 사이드바에 Google API 키를 입력하여 시작하세요.

## 작동 방식: "컨베이어 벨트" 아키텍처

시스템의 데이터 흐름은 산업 현장의 컨베이어 벨트처럼, 최고의 안전성과 효율성을 위해 설계되었습니다.

1.  **분해:** 입력된 SRT 파일은 **메타데이터**와 **데이터**라는 두 가지 별개의 구성 요소로 정밀하게 분해됩니다.
2.  **정제:** 메타데이터는 로컬에 안전하게 보관됩니다. 오직 순수한 텍스트 데이터만이 다음 단계로 진행되어, AI에 의한 메타데이터 오염 가능성을 원천 차단합니다.
3.  **일괄 처리:** 텍스트는 사용자가 정의한 크기의 청크로 그룹화된 후, ID 앵커링 프로토콜을 사용하여 엄격한 JSON 구조로 포맷됩니다.
4.  **재조립:** AI가 번역된 JSON을 반환하면, 시스템은 데이터 무결성을 검증하고 ID를 기준으로 재정렬한 뒤, 원본 그대로 보존된 메타데이터와 꼼꼼하게 재결합하여 완벽하게 동기화된 최종 자막 파일을 생성합니다.

## 핵심 기술: AI 통신 프로토콜

### 돌파구: 'ID 앵커링'과 JSON 강제 모드의 결합

우리의 프로토콜은 논리적 데이터 구조와 엄격한 API 레벨 명령을 결합하여 텍스트 구조를 변경하려는 LLM의 경향을 무력화합니다.

1.  **ID 앵커링: 구조적 불변성 강제**

    AI가 수정 가능한 단일 텍스트 블록으로 해석할 수 있는 단순한 문자열 리스트 대신, 우리는 객체들의 배열을 전송합니다. 각 객체는 고유하고 순차적인 `id`로 "고정"됩니다.

    **AI에 전송되는 데이터 구조:**
    ```json
    [
      {"id": 0, "text": "첫 번째 줄 텍스트."},
      {"id": 1, "text": "두 번째 줄 텍스트."},
      {"id": 2, "text": "세 번째 줄 텍스트."}
    ]
    ```

    이 구조는 논리적 '족쇄' 역할을 합니다. AI는 프롬프트를 통해 각 객체의 `id`를 보존하도록 지시받습니다. 이 간단한 규칙은 다음과 같은 중대한 결과를 낳습니다.
    *   **병합 불가능:** AI는 `id: 1`을 파괴하거나 유효하지 않은 구조를 만들지 않고서는 1번과 2번 줄을 단일 번역 객체로 합칠 수 없습니다.
    *   **분할 불가능:** AI는 새로운 ID를 날조하지 않고서는 3번 줄을 두 개의 번역 객체로 나눌 수 없으며, 이는 지시 사항 위반입니다.

    이것은 텍스트 내용과 관계없이 입력과 출력 객체 간의 엄격한 **1:1 매핑**을 구조적 수준에서 강제합니다. AI가 응답에서 객체의 순서를 뒤섞더라도, 우리는 불변의 ID를 사용하여 항상 정확한 순서로 안정적으로 재정렬할 수 있습니다.

2.  **API 레벨 JSON 강제 모드: 데이터 무결성 보장**

    ID 앵커링이 구조적 매핑 문제를 해결하지만, AI가 유효하지 않은 JSON을 반환하는 것(예: `"번역 결과입니다: ..."`와 같은 대화체 텍스트 추가)을 막지는 못합니다. 이를 제거하기 위해, 우리는 프롬프트 수준의 요청을 완전히 우회합니다.

    Gemini API 호출 시 `response_mime_type` 매개변수를 `application/json`으로 설정하도록 구성합니다. 이것은 제안이 아니라 API 서버 자체에 대한 **시스템 레벨의 명령**입니다. 이는 서버가 문법적으로 완벽한 JSON 객체 외에는 아무것도 반환하지 않도록 계약적으로 구속합니다. 이로써 `JSONDecodeError`의 가능성이 완벽하게 제거되고 통신 파이프라인은 극도로 견고해집니다.

## 기술 스택

*   **코어 & 로직:** `Python 3.13`, `Streamlit 1.51.0`
*   **AI 엔진 & 통신:** `google-generativeai`, `chardet`
*   **패키징 & 배포:** `PyInstaller 6.17.0`, `UPX 4.2.4`

## 라이선스

This project is licensed under the MIT License.
