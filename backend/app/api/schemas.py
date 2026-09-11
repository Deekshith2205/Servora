from pydantic import BaseModel


class ChatRequest(BaseModel):
    customer_id: int
    message: str


class TraceStepOut(BaseModel):
    agent: str
    output: str


class ChatResponse(BaseModel):
    reply: str
    status: str
    trace: list[TraceStepOut]


class TicketOut(BaseModel):
    id: int
    customer_id: int
    category: str
    subject: str
    message: str
    sentiment: str
    urgency: int
    status: str

    class Config:
        from_attributes = True
