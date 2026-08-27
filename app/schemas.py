from datetime import datetime
from pydantic import BaseModel
from typing import Optional


# Auth
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Subscription / Plans
class Plan(BaseModel):
    id: str
    name: str
    price_monthly: float
    stripe_price_id: str
    calls_per_month: int
    tokens_per_month: int
    projects: int
    features: list[str]


class CurrentPlan(BaseModel):
    plan: str
    name: str
    calls_used: int
    calls_limit: int
    tokens_used: int
    tokens_limit: int
    renews_at: datetime | None = None
    is_trial: bool


class SubscriptionCheckout(BaseModel):
    plan: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class SubscriptionCheckoutResponse(BaseModel):
    plan: str
    checkout_url: Optional[str] = None
    message: str


class PlanChangeRequest(BaseModel):
    plan: str


# API Keys
class APIKeyCreate(BaseModel):
    provider: str
    key_name: str
    api_key: str


class APIKeyResponse(BaseModel):
    id: str
    provider: str
    key_name: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Cost Logging
class CostLogCreate(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    status: str = "success"
    error_message: Optional[str] = None
    project: Optional[str] = None
    cache_hit: bool = False


class CostLogResponse(BaseModel):
    id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    latency_ms: float
    status: str
    error_message: Optional[str]
    project: Optional[str]
    cache_hit: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Dashboard
class DashboardSummary(BaseModel):
    total_cost_today: float
    total_cost_week: float
    total_cost_month: float
    total_calls_today: int
    total_tokens_today: int
    avg_latency_today: float
    error_rate_today: float
    cache_hit_rate: float
    daily_costs: list[dict]
    model_breakdown: list[dict]
    provider_breakdown: list[dict]
    hourly_costs_today: list[dict]


class CostForecast(BaseModel):
    projected_monthly_cost: float
    days_remaining: int
    average_daily_cost: float
    trend: str  # "increasing", "decreasing", "stable"


# Budget
class BudgetCreate(BaseModel):
    daily_limit: float = 0.0
    monthly_limit: float = 0.0
    alert_email: Optional[str] = None
    alert_slack_webhook: Optional[str] = None


class BudgetResponse(BaseModel):
    id: str
    daily_limit: float
    monthly_limit: float
    alert_email: Optional[str]
    alert_slack_webhook: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Alert
class AlertResponse(BaseModel):
    id: str
    alert_type: str
    message: str
    threshold: float
    current_value: float
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Export
class ExportRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    format: str = "csv"


# Model Comparison
class ModelComparison(BaseModel):
    model: str
    provider: str
    avg_cost_per_call: float
    avg_latency: float
    total_calls: int
    total_tokens: int
    success_rate: float


# Paginated logs
class PaginatedLogs(BaseModel):
    logs: list[CostLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
