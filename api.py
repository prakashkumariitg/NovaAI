from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import shutil
import tempfile
from pathlib import Path
import os
import json

from audio_processing import transcribe_audio
from llm_chains import refine_transcript, generate_meeting_record

app = FastAPI(title="AI Meeting Assistant API")

# Mount the static directory to serve the frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/process")
async def process_audio(
    file: UploadFile = File(...),
    api_key: str = Form(None),
    base_url: str = Form(None),
    refinement_model: str = Form(None),
    documentation_model: str = Form(None)
):
    temp_dir = Path(tempfile.mkdtemp(prefix="meeting_assistant_api_"))
    temp_path = temp_dir / file.filename
    
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print("1. Transcribing audio...")
        raw_transcript = transcribe_audio(temp_path)
        
        print("2. Refining transcript...")
        refined_result = refine_transcript(
            raw_transcript,
            refinement_model or os.getenv("REFINEMENT_MODEL", "gpt-4o-mini"),
            api_key=api_key,
            base_url=base_url
        )
        refined_transcript = refined_result["refined_transcript"]
        
        print("3. Generating meeting record...")
        meeting_record = generate_meeting_record(
            refined_transcript,
            documentation_model or os.getenv("DOCUMENTATION_MODEL", "gpt-4o"),
            api_key=api_key,
            base_url=base_url
        )
        
        return JSONResponse({
            "raw_transcript": raw_transcript,
            "refined_transcript": refined_transcript,
            "meeting_record": meeting_record
        })
        
    except Exception as e:
        import traceback; traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
