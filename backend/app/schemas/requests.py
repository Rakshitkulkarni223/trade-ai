from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

TF_PATTERN = "^(1m|5m|15m|30m|1H|4H|1D|1W)$"


class RiskOverrides(BaseModel):
    account_size: Optional[float] = Field(None, gt=0)
    max_risk_per_trade_pct: Optional[float] = Field(None, gt=0, le=10)
    max_position_pct: Optional[float] = Field(None, gt=0, le=100)


class AnalyzeRequest(RiskOverrides):
    symbol: str = Field(min_length=1, max_length=24)
    timeframe: str = Field("1H", pattern=TF_PATTERN)


class ChatRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    timeframe: str = Field("1H", pattern=TF_PATTERN)
    message: str = Field("", max_length=1000)
    action: Optional[str] = Field(None, max_length=24)
    conversation_id: Optional[int] = None
    compare_with: Optional[str] = Field(None, max_length=24)


class ExplainRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    timeframe: str = Field("1H", pattern=TF_PATTERN)
    ref_kind: str = Field(max_length=16)       # liquidity | structure | fvg | plan | indicator
    ref_id: str = Field(max_length=64)


class ScanRequest(BaseModel):
    market: str = "India"
    timeframe: str = Field("1D", pattern=TF_PATTERN)
    filters: list[str] = []
    direction: str = Field("long", pattern="^(long|short)$")
    rules: Optional[dict] = None
    symbols: Optional[list[str]] = Field(None, max_length=80)


class ScreenerQuery(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    timeframe: str = Field("1D", pattern=TF_PATTERN)


class WatchlistAdd(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)


class TrackSetup(RiskOverrides):
    symbol: str = Field(min_length=1, max_length=24)
    timeframe: str = Field("1H", pattern=TF_PATTERN)
    note: Optional[str] = Field(None, max_length=500)
