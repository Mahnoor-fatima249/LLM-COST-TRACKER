from dataclasses import dataclass, asdict


@dataclass
class Plan:
    id: str
    name: str
    price_monthly: float
    stripe_price_id: str
    calls_per_month: int
    tokens_per_month: int
    projects: int
    features: list[str]


def _price_id(name: str, price: float) -> str:
    if price == 0:
        return ""
    return f"price_{name}"


PLANS: dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        price_monthly=0.0,
        stripe_price_id="",
        calls_per_month=500,
        tokens_per_month=10_000_000,
        projects=1,
        features=[
            "Up to 500 API calls / month",
            "10M tokens / month",
            "Real-time dashboard",
            "1 project",
            "Basic reporting",
        ],
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        price_monthly=9.0,
        stripe_price_id=_price_id("pro", 9.0),
        calls_per_month=50_000,
        tokens_per_month=50_000_000,
        projects=5,
        features=[
            "50,000 API calls / month",
            "50M tokens / month",
            "5 projects",
            "Advanced forecasting",
            "Budget alerts & spike detection",
            "CSV / JSON export",
            "Email support",
        ],
    ),
    "business": Plan(
        id="business",
        name="Business",
        price_monthly=29.0,
        stripe_price_id=_price_id("business", 29.0),
        calls_per_month=500_000,
        tokens_per_month=500_000_000,
        projects=20,
        features=[
            "500,000 API calls / month",
            "500M tokens / month",
            "20 projects",
            "Team collaboration",
            "Priority support",
            "All Pro features",
        ],
    ),
}


def get_plan(plan_id: str) -> Plan:
    return PLANS.get(plan_id) or PLANS["free"]


def list_plans() -> list[dict]:
    return [asdict(p) for p in PLANS.values()]
