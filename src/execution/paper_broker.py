"""
Paper trading broker simulation.
Simulates order execution with realistic fills and slippage.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import random
from src.execution.base_broker import (
    BaseBroker, OrderRequest, OrderResponse, OrderStatus, OrderSide, Position
)
from src.utils.logging import get_logger
from config.settings import get_data_sources_config

logger = get_logger(__name__)

class PaperBroker(BaseBroker):
    """
    Simulated broker for paper trading.
    
    Features:
    - Realistic fills with simulated slippage
    - Order tracking
    - Position management
    - No real money at risk
    """
    
    def __init__(self, starting_cash: Decimal = Decimal(100000)):
        """
        Initialize paper broker.
        
        Args:
            starting_cash: Starting cash balance (default $100k)
        """
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, OrderResponse] = {}
        self.connected = False
        
        config = get_data_sources_config()
        self.simulate_slippage = config['brokers']['paper']['simulate_slippage']
        self.slippage_bps = config['brokers']['paper']['slippage_bps']
        
        logger.info(
            "Paper broker initialized",
            starting_cash=float(starting_cash),
            slippage_enabled=self.simulate_slippage,
            slippage_bps=self.slippage_bps
        )
    
    def connect(self) -> bool:
        """Simulate connection."""
        self.connected = True
        logger.info("Paper broker connected")
        return True
    
    def disconnect(self):
        """Simulate disconnection."""
        self.connected = False
        logger.info("Paper broker disconnected")
    
    def is_connected(self) -> bool:
        """Check connection status."""
        return self.connected
    
    def get_account_value(self) -> Decimal:
        """Calculate total account value (cash + positions)."""
        positions_value = sum(
            pos.market_value for pos in self.positions.values()
        )
        return self.cash + positions_value
    
    def get_cash_balance(self) -> Decimal:
        """Get available cash."""
        return self.cash
    
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self.positions.values())
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get specific position by symbol."""
        return self.positions.get(symbol)
    
    def submit_order(self, order: OrderRequest) -> OrderResponse:
        """
        Simulate order execution.
        All orders are filled immediately at market with simulated slippage.
        """
        if not self.connected:
            return OrderResponse(
                order_id=str(uuid.uuid4()),
                broker_order_id="",
                status=OrderStatus.REJECTED,
                filled_qty=0,
                filled_avg_price=None,
                commission=None,
                timestamp=datetime.utcnow(),
                error_message="Broker not connected"
            )
        
        order_id = str(uuid.uuid4())
        
        quote = self.get_quote(order.symbol)
        
        if order.side == OrderSide.BUY:
            base_price = quote['ask']
            if self.simulate_slippage:
                slippage = base_price * Decimal(self.slippage_bps) / Decimal(10000)
                fill_price = base_price + slippage
            else:
                fill_price = base_price
        else:
            base_price = quote['bid']
            if self.simulate_slippage:
                slippage = base_price * Decimal(self.slippage_bps) / Decimal(10000)
                fill_price = base_price - slippage
            else:
                fill_price = base_price
        
        total_value = fill_price * Decimal(order.quantity)
        commission = Decimal(1.00)
        
        if order.side == OrderSide.BUY:
            needed_cash = total_value + commission
            if needed_cash > self.cash:
                return OrderResponse(
                    order_id=order_id,
                    broker_order_id=order_id,
                    status=OrderStatus.REJECTED,
                    filled_qty=0,
                    filled_avg_price=None,
                    commission=None,
                    timestamp=datetime.utcnow(),
                    error_message=f"Insufficient cash: need ${needed_cash}, have ${self.cash}"
                )
            
            self.cash -= needed_cash
            self._add_to_position(order.symbol, order.quantity, fill_price)
        else:
            position = self.positions.get(order.symbol)
            if not position or position.quantity < order.quantity:
                return OrderResponse(
                    order_id=order_id,
                    broker_order_id=order_id,
                    status=OrderStatus.REJECTED,
                    filled_qty=0,
                    filled_avg_price=None,
                    commission=None,
                    timestamp=datetime.utcnow(),
                    error_message=f"Insufficient shares to sell"
                )
            
            self.cash += (total_value - commission)
            self._remove_from_position(order.symbol, order.quantity)
        
        response = OrderResponse(
            order_id=order_id,
            broker_order_id=order_id,
            status=OrderStatus.FILLED,
            filled_qty=order.quantity,
            filled_avg_price=fill_price,
            commission=commission,
            timestamp=datetime.utcnow()
        )
        
        self.orders[order_id] = response
        
        logger.info(
            "Paper order filled",
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=float(fill_price),
            slippage_applied=self.simulate_slippage
        )
        
        return response
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order (no-op since orders fill immediately)."""
        return True
    
    def get_order_status(self, order_id: str) -> Optional[OrderResponse]:
        """Get order status."""
        return self.orders.get(order_id)
    
    def get_quote(self, symbol: str) -> Dict[str, Decimal]:
        """Return live-ish quote using yfinance, fallback to simulated."""
        try:
            import yfinance as yf
            t = yf.Ticker(symbol)
            last = None
            try:
                intraday = t.history(period="1d", interval="1m")
                if not intraday.empty and "Close" in intraday.columns:
                    last = float(intraday["Close"].dropna().iloc[-1])
            except Exception:
                pass
            if last is None:
                fi = getattr(t, "fast_info", None)
                if fi and getattr(fi, "last_price", None):
                    last = float(fi.last_price)
            if last is None:
                daily = t.history(period="1d")
                if not daily.empty:
                    last = float(daily["Close"].iloc[-1])
            if last is not None and last > 0:
                mid_price = Decimal(str(last))
                spread = mid_price * Decimal(0.001)
                return {
                    'bid': mid_price - (spread / 2),
                    'ask': mid_price + (spread / 2),
                    'last': mid_price,
                    'volume': Decimal(1000000)
                }
        except Exception:
            pass
        # Fallback simulated
        base_price = Decimal(100)
        random_factor = Decimal(random.uniform(0.95, 1.05))
        mid_price = base_price * random_factor
        spread = mid_price * Decimal(0.001)
        return {
            'bid': mid_price - (spread / 2),
            'ask': mid_price + (spread / 2),
            'last': mid_price,
            'volume': Decimal(1000000)
        }
    
    def _add_to_position(self, symbol: str, quantity: int, price: Decimal):
        """Add to or create position."""
        if symbol in self.positions:
            pos = self.positions[symbol]
            new_qty = pos.quantity + quantity
            new_avg = ((pos.avg_entry_price * Decimal(pos.quantity)) +
                      (price * Decimal(quantity))) / Decimal(new_qty)
            pos.quantity = new_qty
            pos.avg_entry_price = new_avg
            pos.market_value = price * Decimal(new_qty)
            pos.current_price = price
            pos.unrealized_pnl = (price - new_avg) * Decimal(new_qty)
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_entry_price=price,
                current_price=price,
                market_value=price * Decimal(quantity),
                unrealized_pnl=Decimal(0)
            )
    
    def _remove_from_position(self, symbol: str, quantity: int):
        """Remove from position."""
        pos = self.positions[symbol]
        pos.quantity -= quantity
        pos.market_value = pos.current_price * Decimal(pos.quantity)
        pos.unrealized_pnl = (pos.current_price - pos.avg_entry_price) * Decimal(pos.quantity)
        
        if pos.quantity == 0:
            del self.positions[symbol]
