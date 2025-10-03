# from fastapi import FastAPI, HTTPException
# from fastapi.responses import StreamingResponse
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel, Field
# from typing import Literal, Optional, AsyncGenerator
# import json
# import asyncio
# from queue import Queue
# from threading import Thread

# from deepResearch2 import research_legal_query, research_legal_query_streaming

# app = FastAPI(
#     title="Indian Legal Research API",
#     description="AI-powered legal research agent for Indian law with streaming JSON responses",
#     version="1.0.0"
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# class ResearchRequest(BaseModel):
#     query: str = Field(..., description="Legal question or research topic", min_length=1)
#     mode: Literal["normal", "detailed"] = Field(
#         default="normal",
#         description="Research mode: 'normal' for optimal response, 'detailed' for comprehensive analysis"
#     )
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "query": "Can a private company take a loan from an LLP under Indian law?",
#                 "mode": "normal"
#             }
#         }


# class HealthResponse(BaseModel):
#     status: str
#     service: str
#     version: str


# def run_research_in_thread(query: str, mode: str, result_queue: Queue):
#     """Execute research in separate thread"""
#     try:
#         result = research_legal_query(query=query, verbose=False, mode=mode)
#         result_queue.put({"success": True, "data": result})
#     except Exception as e:
#         result_queue.put({"success": False, "error": str(e)})


# async def stream_research_result(query: str, mode: str) -> AsyncGenerator[str, None]:
#     """Stream research results as they become available"""
    
#     result_queue = Queue()
#     thread = Thread(target=run_research_in_thread, args=(query, mode, result_queue))
#     thread.start()
    
#     timeout = 300
#     start_time = asyncio.get_event_loop().time()
    
#     while thread.is_alive():
#         current_time = asyncio.get_event_loop().time()
#         if current_time - start_time > timeout:
#             yield json.dumps({
#                 "error": "Request timeout",
#                 "details": "Research took longer than 5 minutes"
#             }) + "\n"
#             return
        
#         await asyncio.sleep(0.5)
    
#     thread.join()
    
#     if not result_queue.empty():
#         result = result_queue.get()
        
#         if result["success"]:
#             try:
#                 parsed = json.loads(result["data"])
#                 yield json.dumps(parsed, indent=2) + "\n"
#             except json.JSONDecodeError:
#                 yield json.dumps({
#                     "error": "Invalid JSON response",
#                     "raw_response": result["data"]
#                 }) + "\n"
#         else:
#             yield json.dumps({
#                 "error": "Research execution failed",
#                 "details": result.get("error", "Unknown error")
#             }) + "\n"
#     else:
#         yield json.dumps({
#             "error": "No response generated",
#             "details": "Agent completed but produced no output"
#         }) + "\n"


# def run_streaming_research_in_thread(query: str, mode: str, event_queue: Queue):
#     """Execute streaming research in separate thread"""
#     try:
#         for event in research_legal_query_streaming(query=query, mode=mode):
#             event_queue.put({"type": "event", "data": event})
#         event_queue.put({"type": "done"})
#     except Exception as e:
#         event_queue.put({"type": "error", "error": str(e)})


# async def stream_research_progress(query: str, mode: str) -> AsyncGenerator[str, None]:
#     """Stream research progress and final results in real-time"""
    
#     event_queue = Queue()
#     thread = Thread(target=run_streaming_research_in_thread, args=(query, mode, event_queue))
#     thread.start()
    
#     timeout = 300
#     start_time = asyncio.get_event_loop().time()
    
#     while True:
#         current_time = asyncio.get_event_loop().time()
#         if current_time - start_time > timeout:
#             yield f"data: {json.dumps({'type': 'error', 'data': 'Request timeout after 5 minutes'})}\n\n"
#             break
        
#         if not event_queue.empty():
#             item = event_queue.get()
            
#             if item["type"] == "done":
#                 break
#             elif item["type"] == "error":
#                 yield f"data: {json.dumps({'type': 'error', 'data': item['error']})}\n\n"
#                 break
#             elif item["type"] == "event":
#                 event_data = item["data"]
#                 yield f"data: {json.dumps(event_data)}\n\n"
#         else:
#             await asyncio.sleep(0.1)
    
#     thread.join(timeout=5)


# @app.post(
#     "/research",
#     response_class=StreamingResponse,
#     summary="Perform legal research",
#     description="Execute legal research query and return structured JSON with content and references"
# )
# async def research_endpoint(request: ResearchRequest):
#     """
#     Perform legal research on Indian law topics.
    
#     Returns a JSON structure with:
#     - content: Array of text segments with reference IDs
#     - references: Dictionary of all cited sources with URLs
#     """
    
#     if not request.query.strip():
#         raise HTTPException(status_code=400, detail="Query cannot be empty")
    
#     return StreamingResponse(
#         stream_research_result(request.query, request.mode),
#         media_type="application/json"
#     )


# @app.post(
#     "/research/stream",
#     response_class=StreamingResponse,
#     summary="Perform legal research with streaming progress",
#     description="Execute legal research with real-time progress updates and final JSON response"
# )
# async def research_streaming_endpoint(request: ResearchRequest):
#     """
#     Perform legal research on Indian law topics with streaming progress updates.
    
#     Uses Server-Sent Events (SSE) to stream:
#     - Progress updates as research executes
#     - Status messages from each agent node
#     - Final JSON response with content and references
    
#     Event types:
#     - status: Initialization and query processing messages
#     - progress: Node completion updates with details
#     - content: Partial or streaming content (when available)
#     - complete: Final JSON result
#     - error: Error messages if research fails
#     """
    
#     if not request.query.strip():
#         raise HTTPException(status_code=400, detail="Query cannot be empty")
    
#     return StreamingResponse(
#         stream_research_progress(request.query, request.mode),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no"
#         }
#     )


# @app.get(
#     "/health",
#     response_model=HealthResponse,
#     summary="Health check",
#     description="Check if the API service is running"
# )
# async def health_check():
#     """Health check endpoint"""
#     return HealthResponse(
#         status="healthy",
#         service="Indian Legal Research API",
#         version="1.0.0"
#     )


# @app.get("/")
# async def root():
#     """API information and available endpoints"""
#     return {
#         "service": "Indian Legal Research API",
#         "version": "1.0.0",
#         "description": "AI-powered legal research for Indian law with URL verification",
#         "endpoints": {
#             "POST /research": "Perform legal research and return final JSON result",
#             "POST /research/stream": "Perform legal research with real-time streaming progress (SSE)",
#             "GET /health": "Health check",
#             "GET /docs": "Interactive API documentation"
#         },
#         "modes": {
#             "normal": "Optimal, concise research response",
#             "detailed": "Comprehensive, extensive analysis"
#         },
#         "features": [
#             "Automatic URL verification for all references",
#             "Multi-agent research with specialized subagents",
#             "Real-time streaming progress updates",
#             "Structured JSON output with citations"
#         ],
#         "timeout": "5 minutes per request"
#     }


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         app,
#         host="0.0.0.0",
#         port=8001,
#         timeout_keep_alive=600,
#         log_level="info"
#     )


from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal, Optional, AsyncGenerator
import json
import asyncio
from queue import Queue
from threading import Thread
import sys

from deepResearch2 import research_legal_query, research_legal_query_streaming

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
    
    try:
        while thread.is_alive():
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > timeout:
                yield json.dumps({
                    "error": "Request timeout",
                    "details": "Research took longer than 5 minutes"
                }) + "\n"
                return
            
            await asyncio.sleep(0.5)
        
        thread.join()
        
        if not result_queue.empty():
            result = result_queue.get()
            
            if result["success"]:
                try:
                    parsed = json.loads(result["data"])
                    yield json.dumps(parsed, indent=2) + "\n"
                except json.JSONDecodeError:
                    yield json.dumps({
                        "error": "Invalid JSON response",
                        "raw_response": result["data"]
                    }) + "\n"
            else:
                yield json.dumps({
                    "error": "Research execution failed",
                    "details": result.get("error", "Unknown error")
                }) + "\n"
        else:
            yield json.dumps({
                "error": "No response generated",
                "details": "Agent completed but produced no output"
            }) + "\n"
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        pass


def run_streaming_research_in_thread(query: str, mode: str, event_queue: Queue):
    """Execute streaming research in separate thread"""
    try:
        for event in research_legal_query_streaming(query=query, mode=mode):
            event_queue.put({"type": "event", "data": event})
        event_queue.put({"type": "done"})
    except Exception as e:
        event_queue.put({"type": "error", "error": str(e)})


async def stream_research_progress(query: str, mode: str) -> AsyncGenerator[str, None]:
    """Stream research progress and final results in real-time"""
    
    event_queue = Queue()
    thread = Thread(target=run_streaming_research_in_thread, args=(query, mode, event_queue))
    thread.start()
    
    timeout = 300
    start_time = asyncio.get_event_loop().time()
    
    try:
        while True:
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > timeout:
                yield f"data: {json.dumps({'type': 'error', 'data': 'Request timeout after 5 minutes'})}\n\n"
                break
            
            if not event_queue.empty():
                item = event_queue.get()
                
                if item["type"] == "done":
                    break
                elif item["type"] == "error":
                    yield f"data: {json.dumps({'type': 'error', 'data': item['error']})}\n\n"
                    break
                elif item["type"] == "event":
                    event_data = item["data"]
                    yield f"data: {json.dumps(event_data)}\n\n"
            else:
                await asyncio.sleep(0.1)
        
        thread.join(timeout=5)
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        pass


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


@app.post(
    "/research/stream",
    response_class=StreamingResponse,
    summary="Perform legal research with streaming progress",
    description="Execute legal research with real-time progress updates and final JSON response"
)
async def research_streaming_endpoint(request: ResearchRequest):
    """
    Perform legal research on Indian law topics with streaming progress updates.
    
    Uses Server-Sent Events (SSE) to stream:
    - Progress updates as research executes
    - Status messages from each agent node
    - Final JSON response with content and references
    
    Event types:
    - status: Initialization and query processing messages
    - progress: Node completion updates with details
    - content: Partial or streaming content (when available)
    - complete: Final JSON result
    - error: Error messages if research fails
    """
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    return StreamingResponse(
        stream_research_progress(request.query, request.mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
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
        "description": "AI-powered legal research for Indian law with URL verification",
        "endpoints": {
            "POST /research": "Perform legal research and return final JSON result",
            "POST /research/stream": "Perform legal research with real-time streaming progress (SSE)",
            "GET /health": "Health check",
            "GET /docs": "Interactive API documentation"
        },
        "modes": {
            "normal": "Optimal, concise research response",
            "detailed": "Comprehensive, extensive analysis"
        },
        "features": [
            "Automatic URL verification for all references",
            "Multi-agent research with specialized subagents",
            "Real-time streaming progress updates",
            "Structured JSON output with citations"
        ],
        "timeout": "5 minutes per request"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        timeout_keep_alive=600,
        log_level="info"
    )