from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, AwareDatetime

class Operation(BaseModel):
    source_id: str = Field(min_length=1, max_length=100)
    event_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    asset_id: str = Field(min_length=1, max_length=100)
    event_time: AwareDatetime
    command: str = Field(min_length=1, max_length=10000)
    exit_code: int | None = None
class Batch(BaseModel):
    events: list[Operation] = Field(min_length=1, max_length=100)
class Assessment(BaseModel):
    assessment: Literal['normal', 'suspicious', 'insufficient']
    severity: Literal['low', 'medium', 'high', 'critical']
    summary: str = Field(max_length=2000)
    evidence_ids: list[int] = Field(max_length=50)
    recommended_checks: list[str] = Field(max_length=10)
class Feedback(BaseModel):
    status: Literal['acknowledged', 'confirmed', 'false_positive', 'closed']
    comment: str = Field(min_length=1, max_length=2000)
