
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional
class TransactionCreate(BaseModel):
    manager : str
    amount : float
class TransactionRead(TransactionCreate):
    id : int
    model_config = ConfigDict(from_attributes=True)
class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)

class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    content: Optional[str] = Field(None, min_length=1)

class NoteRead(NoteCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)