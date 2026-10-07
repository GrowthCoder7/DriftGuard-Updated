from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    model: str
    messages: list
    max_tokens: int | None = None

@app.post("/v1/chat")
def chat_endpoint(req: ChatRequest):
    if req.model != "acme-pro-2025-01":
        raise HTTPException(status_code=400, detail="Unsupported model")
    # To demonstrate failure later, renaming this field to max_output_tokens will break clients
    if req.max_tokens is None:
        raise HTTPException(status_code=400, detail="max_tokens required")
    return {"choices": [{"message": {"content": "Demo response"}}]}