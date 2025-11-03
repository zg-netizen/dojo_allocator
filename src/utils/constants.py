"""
Application constants to replace magic numbers throughout the codebase.
"""
from decimal import Decimal

# Default values
DEFAULT_STARTING_CASH = Decimal('100000.00')
DEFAULT_COMMISSION = Decimal('1.00')
DEFAULT_PORTFOLIO_VALUE = 100000.0

# Signal processing limits
MAX_SIGNALS_TO_PROCESS = 20
MAX_SIGNALS_TO_DISPLAY = 10
MAX_SIGNALS_FOR_ALLOCATION = 20

# Position limits
MAX_POSITIONS_PER_ROUND = 10
MIN_POSITION_VALUE = Decimal('100.00')

# Time constants (in days)
DEFAULT_ROUND_DURATION_DAYS = 30
MAX_HOLDING_PERIOD_DAYS = 90
CLEAN_ROUNDS_FOR_FULL_RESTORE = 10

# Price simulation
DEFAULT_SIMULATED_PRICE = Decimal('100.00')
PRICE_VOLATILITY_FACTOR = 0.02  # 2% volatility
BID_ASK_SPREAD_FACTOR = 0.001   # 0.1% spread

# Symbol-based default prices for simulation
SYMBOL_DEFAULT_PRICES = {
    'AAPL': Decimal('150.00'),
    'MSFT': Decimal('300.00'),
    'GOOGL': Decimal('2800.00'),
    'AMZN': Decimal('3200.00'),
    'TSLA': Decimal('800.00'),
    'NVDA': Decimal('450.00'),
    'META': Decimal('350.00'),
    'NFLX': Decimal('450.00'),
}

# API timeouts
API_TIMEOUT_SHORT = 5
API_TIMEOUT_MEDIUM = 30
API_TIMEOUT_LONG = 60

# Database query limits
DEFAULT_QUERY_LIMIT = 50
MAX_QUERY_LIMIT = 500

# Performance thresholds
EXCELLENT_RETURN_THRESHOLD = Decimal('0.15')  # 15%
GOOD_RETURN_THRESHOLD = Decimal('0.08')       # 8%
SATISFACTORY_RETURN_THRESHOLD = Decimal('0.05')  # 5%
