from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal, Optional, AsyncGenerator
import json
import asyncio
from queue import Queue
from threading import Thread

from deepResearch import research_legal_query

app = FastAPI(
    title="Indian Legal Research API",
    description="AI-powered legal research agent for Indian law with streaming JSON responses",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str = Field(..., description="Legal question or research topic", min_length=1)
    mode: Literal["normal", "detailed"] = Field(
        default="normal",
        description="Research mode: 'normal' for optimal response, 'detailed' for comprehensive analysis"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Can a private company take a loan from an LLP under Indian law?",
                "mode": "normal"
            }
        }


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


def run_research_in_thread(query: str, mode: str, result_queue: Queue):
    """Execute research in separate thread"""
    try:
        result = research_legal_query(query=query, verbose=False, mode=mode)
        result_queue.put({"success": True, "data": result})
    except Exception as e:
        result_queue.put({"success": False, "error": str(e)})


async def stream_research_result(query: str, mode: str) -> AsyncGenerator[str, None]:
    """Stream research results as they become available"""
    
    result_queue = Queue()
    thread = Thread(target=run_research_in_thread, args=(query, mode, result_queue))
    thread.start()
    
    timeout = 300
    start_time = asyncio.get_event_loop().time()
    
    while thread.is_alive():
        current_time = asyncio.get_event_loop().time()
        if current_time - start_time > timeout:
            yield json.dumps({
                "error": "Request timeout",
                "details": "Research took longer than 5 minutes"
            })
            return
        
        await asyncio.sleep(0.5)
    
    thread.join()
    
    if not result_queue.empty():
        result = result_queue.get()
        
        if result["success"]:
            try:
                parsed = json.loads(result["data"])
                yield json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                yield json.dumps({
                    "error": "Invalid JSON response",
                    "raw_response": result["data"]
                })
        else:
            yield json.dumps({
                "error": "Research execution failed",
                "details": result.get("error", "Unknown error")
            })
    else:
        yield json.dumps({
            "error": "No response generated",
            "details": "Agent completed but produced no output"
        })


@app.post(
    "/research",
    response_class=StreamingResponse,
    summary="Perform legal research",
    description="Execute legal research query and return structured JSON with content and references"
)
async def research_endpoint(request: ResearchRequest):
    """
    Perform legal research on Indian law topics.
    
    Returns a JSON structure with:
    - content: Array of text segments with reference IDs
    - references: Dictionary of all cited sources with URLs
    """
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    return StreamingResponse(
        stream_research_result(request.query, request.mode),
        media_type="application/json"
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API service is running"
)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="Indian Legal Research API",
        version="1.0.0"
    )


@app.get("/")
async def root():
    """API information and available endpoints"""
    return {
        "service": "Indian Legal Research API",
        "version": "1.0.0",
        "description": "AI-powered legal research for Indian law",
        "endpoints": {
            "POST /research": "Perform legal research (supports 'normal' and 'detailed' modes)",
            "GET /health": "Health check",
            "GET /docs": "Interactive API documentation"
        },
        "modes": {
            "normal": "Optimal, concise research response",
            "detailed": "Comprehensive, extensive analysis"
        },
        "timeout": "5 minutes per request"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        timeout_keep_alive=600,
        log_level="info"
    )