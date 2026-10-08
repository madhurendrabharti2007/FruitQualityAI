"""Typed API contracts."""
from pydantic import BaseModel, Field

class Info(BaseModel):
    title: str
    points: list[str]
    disposal_tip: str | None = None

class TopPrediction(BaseModel):
    fruit: str
    score: float = Field(ge=0, le=1)

class PredictionResponse(BaseModel):
    fruit: str
    status: str
    confidence: float = Field(ge=0, le=100)
    info: Info
    demo: bool = False
    ripeness_stage: str = "ripe"
    shelf_life_estimate: str = "2-4 days"
    top_predictions: list[TopPrediction] = Field(default_factory=list)

class NotRecognizedResponse(BaseModel):
    status: str
    message: str
    top_predictions: list[TopPrediction] = Field(default_factory=list)

class FruitResponse(BaseModel):
    name: str
    benefits: list[str]
    harms: list[str]
    disposal_tip: str
    sample_image: str | None = None

class FruitCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    benefits: list[str] = Field(default_factory=list)
    harms: list[str] = Field(default_factory=list)
    disposal_tip: str = Field(default="Seal spoiled fruit in a bag and place it in organic waste.", max_length=500)
    sample_image: str | None = None

class AuthInput(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: str
    role: str = "customer"
    access_token: str | None = None

class HistoryResponse(BaseModel):
    id: int
    fruit: str
    status: str
    confidence: float
    image_url: str | None = None
    created_at: str
    ripeness_stage: str = "ripe"
    shelf_life_estimate: str = "2-4 days"

class BatchItemResponse(BaseModel):
    filename: str
    fruit: str | None = None
    status: str
    confidence: float = 0
    ripeness_stage: str = "not_recognized"
    shelf_life_estimate: str = "-"
    image_url: str | None = None

class BatchResponse(BaseModel):
    batch_id: str
    created_at: str
    total: int
    fresh_count: int
    rotten_count: int
    not_recognized_count: int
    fresh_percentage: float
    rotten_percentage: float
    items: list[BatchItemResponse]

class VendorRequestResponse(BaseModel):
    role: str
    message: str

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None

class ChatResponse(BaseModel):
    reply: str
    conversation_id: str

class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)

class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=8, max_length=128)
