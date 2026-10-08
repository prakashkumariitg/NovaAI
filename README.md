# NovaAI - AI Meeting Assistant

![NovaAI Pipeline](https://img.shields.io/badge/Architecture-FastAPI%20%2B%20HTML-0A0E27?style=flat-square&logo=fastapi)
![Models](https://img.shields.io/badge/Models-Whisper%20%7C%20Groq%20LLMs-14B8A6?style=flat-square)

NovaAI is an end-to-end meeting assistant that transforms uploaded audio recordings into highly accurate, structured meeting records. 

It satisfies all ML Bootcamp Problem Statement constraints, including strict anti-hallucination guardrails that ensure missing action item owners or deadlines are explicitly marked as `Unspecified`.

## 🎥 Demonstration Video
**[Click here to watch the full end-to-end demonstration video](https://drive.google.com/file/d/1HzktXo8VJhSuJ44VvV3o9ZObw6YqjPCl/view?usp=sharing)**

---

## 🏗 System Architecture & Workflow

The application connects a modern **FastAPI** backend to a custom **Single Page Application (SPA)**. It runs a distinct 3-stage multimodal AI pipeline.

```mermaid
flowchart TD
    classDef frontend fill:#0A0E27,stroke:#4F46E5,stroke-width:2px,color:#fff;
    classDef backend fill:#111633,stroke:#14B8A6,stroke-width:2px,color:#fff;
    classDef model fill:#1A1F3D,stroke:#8B5CF6,stroke-width:2px,color:#fff;

    Upload([Audio Upload]) --> API[FastAPI Server]
    
    subgraph Pipeline [Multimodal Processing Pipeline]
        API --> A[Audio Validation & Decoding]
        A --> STT[faster-whisper STT]
        STT -- Raw Transcript --> REF[Refinement LLM]
        REF -- Domain-aware Correction --> DOC[Documentation LLM]
    end

    DOC -- JSON Meeting Record --> UI[Animated Results UI]
    
    subgraph Outputs [Downloadable Formats]
        UI -.-> MD[.md Export]
        UI -.-> TXT[.txt Export]
        UI -.-> CSV[.csv Export]
    end

    class Upload,UI,MD,TXT,CSV frontend;
    class API,A backend;
    class STT,REF,DOC model;
```

### Ordered Processing Workflow
1. **Audio processing:** The uploaded recording is validated and processed locally. `faster-whisper` (`base.en` by default) transcribes the audio, producing the raw English transcript.
2. **Transcript refinement:** A dedicated Language Model processes the raw transcript, correcting speech-recognition errors (especially domain-specific terms and acronyms) and returning a clean, highly readable transcript without altering the original meaning.
3. **Meeting documentation:** A separate, more capable documentation Language Model converts the refined transcript into a highly structured JSON record containing an executive summary, chronological minutes, explicit decisions, and concrete action items.

### Models Utilized
- **Speech-to-Text Model:** `faster-whisper` (`base.en`). Runs locally and is optimized for English transcription speed and accuracy.
- **Transcript Refinement Model:** `openai/gpt-oss-20b` (via Groq API). A fast, highly capable open-source model tasked specifically with proofreading and terminology correction while strictly preserving intent, names, numbers, and negations.
- **Meeting Documentation Model:** `openai/gpt-oss-120b` (via Groq API). A powerful, high-parameter model tasked with deep semantic extraction. It synthesizes accurate minutes, decisions, and tasks, strictly following anti-hallucination guardrails (e.g., outputting `Unspecified` for missing owners/deadlines).

*All model names and endpoints are fully configurable via the `.env` file.*

## 🧩 Module Breakdown
- `static/index.html`: A custom SPA frontend featuring real-time pipeline status and inline error handling.
- `api.py`: FastAPI backend that runs the multimodal processing pipeline and serves the frontend.
- `audio_processing.py`: Audio validation and local transcription using `faster-whisper`.
- `llm_chains.py`: Manages the separate LLM stages for transcript refinement and documentation generation.
- `prompts.py`: Optimized system prompts enforcing strict extraction rules and anti-hallucination constraints.

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- FFmpeg installed on your system

### 1. Local Setup
Clone the repository and install dependencies:
```bash
git clone https://github.com/prakashkumariitg/NovaAI.git
cd NovaAI
python -m venv .venv
# Windows: .venv\Scriptsctivate
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file in the project root and add your Groq API key:
```ini
GROQ_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.groq.com/openai/v1
REFINEMENT_MODEL=openai/gpt-oss-20b
DOCUMENTATION_MODEL=openai/gpt-oss-120b
```

### 3. Run the App
```bash
python api.py
```
Open `http://localhost:8000` in your web browser. 

---

## 🐳 Docker Deployment

A `Dockerfile` is included for containerized deployment.
```bash
docker build -t nova-ai .
docker run -p 8000:8000 --env-file .env nova-ai
```
Visit `http://localhost:8000`.

## 📁 Submission Assets
The sample meeting audio recording and all generated JSON/Markdown outputs are located in the `Meeting_Audio_And_with_Items` folder.
