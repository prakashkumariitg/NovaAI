# NovaAI — AI Meeting Assistant

![NovaAI Pipeline](https://img.shields.io/badge/Architecture-FastAPI%20%2B%20HTML-0A0E27?style=flat-square&logo=fastapi)
![Models](https://img.shields.io/badge/Models-Whisper%20%7C%20Groq%20LLMs-14B8A6?style=flat-square)

NovaAI is a production-ready meeting-assistant workflow that transforms uploaded English-language audio recordings into highly accurate, structured meeting records. 

It satisfies all ML Bootcamp Problem Statement constraints, including strict anti-hallucination guardrails ensuring that missing action item owners or deadlines are explicitly marked as `Unspecified`.

## 🧠 Architecture & Workflow

The application is built on a modern **FastAPI** backend serving a highly interactive, animated **Single Page Application (SPA)**. It orchestrates a coordinated multimodal AI pipeline.

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

### Module Breakdown
- `static/index.html`: A custom, highly animated SPA frontend featuring a glassmorphism UI, real-time pipeline status, and inline error handling.
- `api.py`: FastAPI backend that orchestrates the multimodal processing pipeline and serves the frontend.
- `audio_processing.py`: Audio validation and local transcription using `faster-whisper`.
- `llm_chains.py`: Manages the separate LLM stages for transcript refinement and documentation generation.
- `prompts.py`: Highly optimized system prompts enforcing strict extraction rules and anti-hallucination constraints.

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
# Windows: .venv\Scripts\activate
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