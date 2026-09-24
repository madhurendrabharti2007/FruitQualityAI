"""Grounded fruit question assistant."""
import json
import logging
import os
from pathlib import Path
from uuid import UUID, uuid4
from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import ChatMessage, FruitNotebook, get_db
from app.schemas import ChatRequest, ChatResponse

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)
router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)
MODEL = "gemini-3.6-flash"
SYSTEM_PROMPT = """You are Ripewise's fruit doubt assistant. Answer only questions about fruits, nutrition, freshness, storage, combinations, and food safety. Keep answers concise (2-4 sentences unless the user asks for detail). Use the supplied notebook context when relevant and do not invent facts that conflict with it. For health or medical guidance, add: 'This isn't medical advice; consult a doctor for specific concerns.' Politely decline unrelated questions and steer the user back to fruit topics."""
MISSING_KEY_REPLY = "The fruit assistant is not configured yet. You can browse the Notebook for evidence-based fruit guidance."
ERROR_REPLY = "I couldn't reach the fruit assistant right now. Please try again in a moment."
RATE_LIMIT_REPLY = "The fruit assistant is experiencing high demand right now. Please wait a moment and try again."
_api_key = os.getenv("GEMINI_API_KEY", "")
logger.info("Gemini configuration loaded: env_path=%s, key_present=%s, key_length=%d, model=%s", ENV_PATH, bool(_api_key and not _api_key.startswith("your-")), len(_api_key), MODEL)


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
        client = genai.Client(api_key=api_key)
        transcript = "\n".join(f"{item.role}: {item.content}" for item in history)
        full_prompt = f"Notebook context:\n{context}\n\nRecent conversation:\n{transcript}\n\nuser: {message}"
        logger.info("Sending Gemini request: model=%s, message_length=%d, context_length=%d, history_messages=%d", MODEL, len(message), len(context), len(history))
        text = None
        last_exc = None
        for attempt_model in (MODEL, "gemini-2.0-flash"):
            try:
                try:
                    response = client.models.generate_content(model=attempt_model, contents=full_prompt, config={"system_instruction": SYSTEM_PROMPT})
                    text = getattr(response, "text", None)
                except Exception:
                    combined = f"SYSTEM: {SYSTEM_PROMPT}\n\n{full_prompt}"
                    response = client.models.generate_content(model=attempt_model, contents=combined)
                    text = getattr(response, "text", None)
                if text:
                    break
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).casefold()
                if "429" in str(exc) or "rate" in err_str or "quota" in err_str or "503" in str(exc) or "unavailable" in err_str:
                    raise
                logger.info("Model %s attempt failed (%s), will try fallback model if available", attempt_model, type(exc).__name__)
        if text:
            logger.info("Gemini request succeeded: response_text_present=%s", True)
            return text.strip()
        if last_exc is not None:
            raise last_exc
        return ERROR_REPLY
    except Exception as exc:
        logger.exception("Gemini request failed: exception_type=%s, message=%s", type(exc).__name__, str(exc))
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
