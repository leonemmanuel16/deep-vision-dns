"""
Vision Assistant — Local LLM-powered Q&A about detections.

Endpoint: POST /api/ask
Body: {"question": "..."}
Response: {"answer": "...", "sql": "...", "row_count": N, "raw_data": [...]}
"""

import logging

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from prompt_builder import build_prompt
from query_executor import execute_query, extract_sql
from response_formatter import build_final_response

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("assistant")

app = FastAPI(title="Vision Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sql: str | None = None
    row_count: int = 0
    raw_data: list = []


@app.post("/api/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    """
    Process a natural language question about detections.
    1. Build prompt with DB schema + question
    2. Send to Ollama (Phi-3)
    3. Extract SQL from response
    4. Execute SQL (read-only)
    5. Format and return results
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    logger.info(f"Question: {question}")

    # Step 1: Build prompt
    prompt = build_prompt(question)

    # Step 2: Query Ollama
    try:
        llm_response = await query_ollama(prompt)
        logger.info(f"LLM response length: {len(llm_response)}")
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return AskResponse(
            question=question,
            answer=f"Error al consultar el modelo de IA: {str(e)}",
        )

    # Step 3: Extract SQL
    sql = extract_sql(llm_response)
    if not sql:
        return AskResponse(
            question=question,
            answer="No pude generar una consulta SQL para tu pregunta. Intenta reformularla.",
        )

    logger.info(f"Generated SQL: {sql}")

    # Step 4: Execute
    query_result = execute_query(sql)

    # Step 5: Format
    response = build_final_response(question, sql, query_result, llm_response)

    return AskResponse(**response)


async def query_ollama(prompt: str) -> str:
    """Send prompt to Ollama and get response."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.assistant_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 512,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")


@app.get("/")
def root():
    return {"name": "Vision Assistant", "model": settings.assistant_model, "status": "running"}


@app.get("/api/health")
def health():
    return {"status": "ok"}
