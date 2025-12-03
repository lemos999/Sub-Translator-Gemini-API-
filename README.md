# 🎬 Subtitle Translator (Python Automation)

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange)

---

## 📖 Introduction (English)

**Subtitle Translator** is a Python-based automation tool designed to translate subtitle files (SRT/VTT) while strictly preserving structural metadata.

The core philosophy of this project is **"Structure First, Content Iteration."**
Unlike general text translators that often break timecodes or formatting tags, this tool guarantees the integrity of subtitle metadata. While the current version excels at technical precision, the semantic nuance and narrative flow of the translation are under active development.

### 🎯 Project Scope
- **Input:** Raw subtitle files (`.srt`, `.vtt`).
- **Processing:** Line-by-line parsing with strict separation of logic (timestamps/tags) and content (dialogue).
- **Output:** Translated subtitle files fully compatible with media players.

### 🚀 Key Features

#### ✅ 1. Metadata & Structure Integrity (Stable)
The system utilizes a rigid parsing algorithm to isolate metadata from translatable text.
- **Timecode Preservation:** Ensures exact synchronization with the video source; no drift or offset occurs during translation.
- **Tag Protection:** HTML-style tags (e.g., `<i>`, `<b>`, `<font>`) and positioning identifiers are excluded from the translation engine's processing scope, preventing syntax corruption.
- **Stability:** The generated output is syntactically perfect, ensuring zero playback errors in media players like VLC or IINA.

#### 🚧 2. Narrative Flow & Context (Work in Progress)
While the tool successfully translates individual lines, handling the "Narrative Context" across multiple dialogue lines is a known limitation in the current build.
- **Current State:** Translation operates primarily on a sentence-by-sentence basis. This may result in literal translations that miss the broader situational context or speaker tone.
- **Roadmap:** Future updates will implement a "Context Window" algorithm to analyze surrounding dialogues before translating, improving cohesion and narrative flow.

---

## ⚙️ Installation & Usage (English)

### 1. Prerequisites
- **Python 3.8+**
- **pip** (Python Package Installer)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/lemos999/subtitle-translator.git
cd subtitle-translator

# Create Virtual Environment (Recommended)
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory to store your API keys securely. **Do not hardcode keys in `app.py`.**

```ini
# .env file
OPENAI_API_KEY=your_sk_key_here
TARGET_LANG=Korean
```

### 4. Execution
Run the application via the Command Line Interface (CLI).

```bash
# Basic Usage
python app.py input_movie.srt
```

- **Output:** `input_movie_ko.srt` (Generated in the same directory)
- **Log:** `translation.log` (Check this file for process details and errors)

---
---

## 📖 프로젝트 소개 (Korean)

**Subtitle Translator**는 자막 파일(SRT/VTT)의 구조적 메타데이터를 완벽하게 보존하면서 번역을 수행하는 파이썬 기반 자동화 도구입니다.

이 프로젝트의 핵심 철학은 "구조 우선, 내용 개선(Structure First, Content Iteration)"입니다.
일반적인 번역기가 타임코드나 포맷팅 태그를 손상시키는 문제를 해결하기 위해, 이 도구는 자막의 메타데이터 무결성을 최우선으로 보장합니다. 현재 버전은 기술적 정밀함(메타데이터)에 강점이 있으며, 서사적 맥락(Context)과 뉘앙스 처리는 향후 고도화될 예정입니다.

### 🎯 프로젝트 범위
- **입력:** 원본 자막 파일 (`.srt`, `.vtt`).
- **처리:** 로직(타임코드/태그)과 콘텐츠(대사)를 엄격히 분리하여 파싱 및 번역 수행.
- **출력:** 미디어 플레이어와 완벽하게 호환되는 번역된 자막 파일.

### 🚀 핵심 기능

#### ✅ 1. 메타데이터 및 구조적 무결성 (Stable)
이 시스템은 번역 대상 텍스트와 메타데이터를 분리하는 엄격한 파싱 알고리즘을 사용합니다.
- **타임코드 보존:** 영상 소스와의 정확한 싱크를 보장하며, 번역 과정에서 시간 밀림 현상이 발생하지 않습니다.
- **태그 보호:** `<i>`, `<b>`, `<font>` 등 스타일 태그와 위치 식별자를 번역 엔진의 처리 범위에서 제외하여 구문 오류를 방지합니다.
- **안정성:** 생성된 결과물은 문법적으로 완벽한 자막 포맷을 유지하며, VLC나 IINA 등 플레이어에서 재생 오류가 없습니다.

#### 🚧 2. 서사적 흐름 및 맥락 처리 (Work in Progress)
현재 버전은 개별 라인 번역에는 성공적이나, 여러 대사에 걸친 "서사적 맥락(Narrative Context)" 처리는 아직 개발 단계에 있습니다.
- **현재 상태:** 번역이 주로 문장 단위로 독립적으로 수행됩니다. 이로 인해 상황적 맥락이나 화자의 어조를 놓치는 직역투가 발생할 수 있습니다.
- **향후 계획:** 주변 대사를 함께 분석하여 번역을 수행하는 "Context Window" 알고리즘을 도입하여, 문맥적 연결성과 자연스러운 흐름을 개선할 예정입니다.

---

## ⚙️ 설치 및 사용 방법 (Korean)

### 1. 사전 요구 사항
- **Python 3.8 이상**
- **pip**

### 2. 설치
```bash
# 저장소 복제
git clone https://github.com/lemos999/subtitle-translator.git
cd subtitle-translator

# 가상 환경 생성 (권장)
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# 의존성 패키지 설치
pip install -r requirements.txt
```

### 3. 환경 설정
루트 디렉토리에 `.env` 파일을 생성하여 API 키를 설정합니다. **절대 소스코드(`app.py`)에 키를 직접 입력하지 마십시오.**

```ini
# .env 예시
OPENAI_API_KEY=your_sk_key_here
TARGET_LANG=Korean
```

### 4. 실행
터미널(CLI)에서 아래 명령어로 실행합니다.

```bash
# 기본 실행
python app.py input_movie.srt
```

- **결과물:** `input_movie_ko.srt` (동일 경로에 생성됨)
- **로그:** `translation.log` (에러 발생 시 이 파일을 확인하세요)

---

## 📧 Contact

**Project Maintainer**
- **Email:** lemoaxtoria@gmail.com
- **GitHub:** [lemos999](https://github.com/lemos999)

**Project Link**: [https://github.com/lemos999/subtitle-translator](https://github.com/lemos999/subtitle-translator)

[2025.12.03 (Wed) 15:01:25]
