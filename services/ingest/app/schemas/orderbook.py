"""F1.2 호가창 스키마."""
from pydantic import BaseModel


class OrderLevel(BaseModel):
    price: float
    quantity: int
    count: int = 1


class OrderBookResponse(BaseModel):
    ticker: str
    timestamp: str
    ask_levels: list[OrderLevel]
    bid_levels: list[OrderLevel]
    spread: float
    mid_price: float
    source: str = "simulated"
