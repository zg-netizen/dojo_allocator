"""Prometheus metrics exporters."""
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

# Create registry
registry = CollectorRegistry()

# ========== SIGNAL METRICS ==========
signals_created = Counter(
    'signals_created_total',
    'Total number of signals created',
    ['source'],
    registry=registry
)

signals_active = Gauge(
    'signals_active',
    'Number of active signals',
    ['conviction_tier'],
    registry=registry
)

# ========== POSITION METRICS ==========
positions_opened = Counter(
    'positions_opened_total',
    'Total number of positions opened',
    ['symbol', 'direction'],
    registry=registry
)

positions_closed = Counter(
    'positions_closed_total',
    'Total number of positions closed',
    ['outcome'],
    registry=registry
)

# ========== ORDER METRICS ==========
orders_executed = Counter(
    'orders_executed_total',
    'Total number of orders executed',
    ['side', 'status'],
    registry=registry
)

order_execution_time = Histogram(
    'order_execution_seconds',
    'Order execution time in seconds',
    registry=registry
)

# ========== PORTFOLIO METRICS ==========
portfolio_value = Gauge(
    'portfolio_value_usd',
    'Total portfolio value in USD',
    registry=registry
)

allocation_power = Gauge(
    'allocation_power',
    'Current allocation power (discipline multiplier)',
    registry=registry
)

# ========== PHILOSOPHY METRICS ==========
philosophy_violations = Counter(
    'philosophy_violations_total',
    'Total philosophy rule violations',
    ['rule'],
    registry=registry
)

# ========== HELPER FUNCTIONS ==========
def record_signal_created(source: str):
    """Record a new signal creation."""
    signals_created.labels(source=source).inc()

def record_position_opened(symbol: str, direction: str):
    """Record a new position opening."""
    positions_opened.labels(symbol=symbol, direction=direction).inc()

def record_position_closed(outcome: str):
    """Record a position closing."""
    positions_closed.labels(outcome=outcome).inc()

def record_order_executed(side: str, status: str):
    """Record an order execution."""
    orders_executed.labels(side=side, status=status).inc()

def update_portfolio_value(value: float):
    """Update current portfolio value metric."""
    portfolio_value.set(value)

def update_allocation_power(power: float):
    """Update current allocation power metric."""
    allocation_power.set(power)

def record_philosophy_violation(rule: str):
    """Record a philosophy rule violation."""
    philosophy_violations.labels(rule=rule).inc()
