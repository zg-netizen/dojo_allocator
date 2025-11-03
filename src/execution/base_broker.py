"""
Abstract broker interface.
All broker adapters must implement this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

class OrderSide(str, Enum):
    """Order side (buy or sell)."""
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

class OrderStatus(str, Enum):
    """Order execution status."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass
class OrderRequest:
    """Standardized order request."""
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = "DAY"

@dataclass
class OrderResponse:
    """Standardized order response."""
    order_id: str
    broker_order_id: str
    status: OrderStatus
    filled_qty: int
    filled_avg_price: Optional[Decimal]
    commission: Optional[Decimal]
    timestamp: datetime
    error_message: Optional[str] = None

@dataclass
class Position:
    """Current position snapshot."""
    symbol: str
    quantity: int
    avg_entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal

class BaseBroker(ABC):
    """
    Abstract broker interface.
    All concrete brokers must implement these methods.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker."""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close broker connection."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if broker connection is active."""
        pass
    
    @abstractmethod
    def get_account_value(self) -> Decimal:
        """Get total account value."""
        pass
    
    @abstractmethod
    def get_cash_balance(self) -> Decimal:
        """Get available cash."""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get specific position by symbol."""
        pass
    
    @abstractmethod
    def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit an order to the broker."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderResponse:
        """Get current order status."""
        pass
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, Decimal]:
        """Get current quote for symbol."""
        pass
