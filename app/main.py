from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.rag import ask 

app = FastAPI(
    title="Indo RAG API",
    version="1.0.0",
    description="RAG system using LangChain + Chroma + Indo E5 embeddings"
)

# Request and Response Schema

class AskRequest(BaseModel):
    q: str

class Source(BaseModel):
    document: str
    page: int | str


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]



# Health Check

@app.get("/health")
def health_check():
    return {"status": "ok"}


# RAG Endpoint

@app.post("/ask", response_model=AskResponse)
def ask_question(req: AskRequest):
    question = req.q.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = ask(question)
    return AskResponse(
        answer=result["answer"],
        sources=result["sources"]
    )

