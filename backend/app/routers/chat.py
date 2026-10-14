"""Grounded fruit question assistant."""
import json
import logging
import os
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.config import GEMINI_MODEL, load_backend_env
from app.database import ChatMessage, FruitNotebook, get_db
from app.schemas import ChatRequest, ChatResponse

load_backend_env()
router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)
MODEL = GEMINI_MODEL
SYSTEM_PROMPT = """You are Ripewise's fruit doubt assistant. Answer only questions about fruits, nutrition, freshness, storage, combinations, and food safety. Keep answers concise (2-4 sentences unless the user asks for detail). Use the supplied notebook context when relevant and do not invent facts that conflict with it. For health or medical guidance, add: 'This isn't medical advice; consult a doctor for specific concerns.' Politely decline unrelated questions and steer the user back to fruit topics."""
MISSING_KEY_REPLY = "The fruit assistant is not configured yet. You can browse the Notebook for evidence-based fruit guidance."
ERROR_REPLY = "I couldn't reach the fruit assistant right now. Please try again in a moment."
RATE_LIMIT_REPLY = "The fruit assistant is experiencing high demand right now. Please wait a moment and try again."


def _conversation_id(value: str | None) -> str:
    try:
        return str(UUID(value)) if value else str(uuid4())
    except (ValueError, AttributeError, TypeError):
        return str(uuid4())


def _notebook_context(message: str, db: Session) -> str:
    words = message.casefold()
    matches = [item for item in db.query(FruitNotebook).all() if item.fruit_name.casefold() in words]
    return "\n\n".join(
        f"{item.fruit_name}: {json.dumps({'benefits': json.loads(item.benefits), 'good_combinations': json.loads(item.good_combinations), 'bad_combinations': json.loads(item.bad_combinations), 'overconsumption_risk': item.overconsumption_risk, 'rotten_fruit_harms': json.loads(item.rotten_fruit_harms), 'storage_tip': item.storage_tip})}"
        for item in matches
    ) or "No specific notebook fruit was mentioned."


def _generate_reply(message: str, history: list[ChatMessage], context: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("your-"):
        logger.warning("Gemini request skipped because GEMINI_API_KEY is missing or is still a placeholder")
        return MISSING_KEY_REPLY
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=20_000),
        )
        transcript = "\n".join(f"{item.role}: {item.content}" for item in history)
        full_prompt = f"Notebook context:\n{context}\n\nRecent conversation:\n{transcript}\n\nuser: {message}"
        logger.info("Sending Gemini request: model=%s, message_length=%d, context_length=%d, history_messages=%d", MODEL, len(message), len(context), len(history))
        config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
        response = client.models.generate_content(
            model=MODEL,
            contents=full_prompt,
            config=config,
        )
        text = getattr(response, "text", None)
        if text and text.strip():
            logger.info("Gemini request succeeded: response_text_present=True")
            return text.strip()
        logger.warning("Gemini returned no chat response text.")
        return ERROR_REPLY
    except Exception as exc:
        logger.error("Gemini request failed: exception_type=%s", type(exc).__name__)
        err_str = str(exc).casefold()
        if "429" in str(exc) or "rate" in err_str or "quota" in err_str or "503" in str(exc) or "unavailable" in err_str or "demand" in err_str:
            return RATE_LIMIT_REPLY
        return ERROR_REPLY


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    conversation_id = _conversation_id(payload.conversation_id)
    history = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at.desc()).limit(10).all()
    history.reverse()
    db.add(ChatMessage(conversation_id=conversation_id, role="user", content=payload.message.strip()))
    reply = _generate_reply(payload.message.strip(), history, _notebook_context(payload.message, db))
    db.add(ChatMessage(conversation_id=conversation_id, role="model", content=reply))
    db.commit()
    return {"reply": reply, "conversation_id": conversation_id}
