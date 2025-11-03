"""
Signal Quality Filters

This module provides quality filters to reject low-quality signals before scoring.
Filters include price, volume, staleness, and transaction value checks.
"""

from datetime import datetime, timedelta
from typing import Optional
from decimal import Decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)

class SignalQualityFilter:
    """Apply quality filters to reject low-quality signals."""
    
    def __init__(self):
        # Quality thresholds
        self.MIN_PRICE = Decimal('5.00')  # Reject penny stocks
        self.MIN_TRANSACTION_VALUE = Decimal('10000.00')  # Reject small trades
        self.MAX_STALENESS_DAYS = 30  # Reject old congressional trades
        self.MIN_AVG_VOLUME_USD = 5_000_000  # Reject illiquid stocks
        
        # Initialize market data provider
        try:
            from src.data.market_data import MarketDataProvider, MarketDataFilter
            self.market_data_provider = MarketDataProvider()
            self.market_data_filter = MarketDataFilter(self.market_data_provider)
            self.market_data_enabled = True
            logger.info("Market data integration enabled")
        except Exception as e:
            logger.warning(f"Market data integration disabled: {e}")
            self.market_data_provider = None
            self.market_data_filter = None
            self.market_data_enabled = False
        
    def apply_quality_filters(self, signal_data: dict) -> tuple[bool, Optional[str]]:
        """
        Apply hard filters to reject low-quality signals.
        
        Args:
            signal_data: Signal data dictionary
            
        Returns:
            Tuple of (passes_filter, rejection_reason)
        """
        
        # 1. Price filter: Reject penny stocks
        if signal_data.get('price'):
            try:
                price = Decimal(str(signal_data['price']))
                if price < self.MIN_PRICE:
                    return False, f"PRICE_TOO_LOW: ${price} < ${self.MIN_PRICE}"
            except (ValueError, TypeError):
                pass  # Skip if price parsing fails
        
        # 2. Transaction value filter: Reject small trades
        if signal_data.get('transaction_value'):
            try:
                value = Decimal(str(signal_data['transaction_value']))
                if value < self.MIN_TRANSACTION_VALUE:
                    return False, f"TRANSACTION_TOO_SMALL: ${value:,.0f} < ${self.MIN_TRANSACTION_VALUE:,.0f}"
            except (ValueError, TypeError):
                pass  # Skip if value parsing fails
        
        # 3. Staleness filter: Reject old congressional trades
        if signal_data.get('source') == 'congressional':
            filing_date = signal_data.get('filing_date')
            if filing_date:
                try:
                    if isinstance(filing_date, str):
                        filing_date = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))
                    
                    days_since_filing = (datetime.utcnow() - filing_date.replace(tzinfo=None)).days
                    if days_since_filing > self.MAX_STALENESS_DAYS:
                        return False, f"STALE_SIGNAL: {days_since_filing} days old > {self.MAX_STALENESS_DAYS} days"
                except (ValueError, TypeError, AttributeError):
                    pass  # Skip if date parsing fails
        
        # 4. Form 4 specific filters
        if signal_data.get('source') == 'form4':
            # Reject if not a purchase (already filtered in fetcher, but double-check)
            if signal_data.get('transaction_code') != 'P':
                return False, "NOT_PURCHASE: Form 4 must be purchase"
            
            # Reject if no transaction value
            if not signal_data.get('transaction_value', 0):
                return False, "NO_TRANSACTION_VALUE: Form 4 missing value"
        
        # 5. Symbol validation: Reject empty or invalid symbols
        symbol = signal_data.get('symbol', '').strip()
        if not symbol or len(symbol) > 10:
            return False, f"INVALID_SYMBOL: '{symbol}'"
        
        # 6. Filer validation: Reject signals without filer name
        filer_name = signal_data.get('filer_name', '').strip()
        if not filer_name:
            return False, "NO_FILER_NAME: Missing insider/congressional name"
        
        # 7. Market data filters (if enabled)
        if self.market_data_enabled and self.market_data_filter:
            market_passes, market_reason = self.market_data_filter.apply_market_data_filters(signal_data)
            if not market_passes:
                return False, f"MARKET_DATA: {market_reason}"
        
        return True, None
    
    def calculate_recency_score(self, signal_data: dict) -> float:
        """
        Calculate recency score with exponential decay.
        
        Half-life = 18 days (score drops to 0.5 after 18 days)
        """
        filing_date = signal_data.get('filing_date')
        if not filing_date:
            return 0.5  # Default score for missing dates
        
        try:
            if isinstance(filing_date, str):
                filing_date = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))
            
            days_since_filing = (datetime.utcnow() - filing_date.replace(tzinfo=None)).days
            
            # Exponential decay: score = exp(-λ × days)
            # λ = ln(2) / half_life = 0.693 / 18 = 0.0385
            lambda_decay = 0.0385
            
            decay_factor = 2.718281828 ** (-lambda_decay * days_since_filing)
            
            # Base recency score (1.0 for today, declining over time)
            base_score = 1.0 - (days_since_filing / 90.0)  # Linear component
            base_score = max(0, base_score)
            
            # Apply exponential decay
            final_score = base_score * decay_factor
            
            return min(1.0, max(0.0, final_score))
            
        except (ValueError, TypeError, AttributeError):
            return 0.5  # Default score for parsing errors
    
    def get_insider_quality_multiplier(self, signal_data: dict) -> float:
        """
        Weight signals by insider position quality.
        
        CEO/CFO buys = strongest signal
        Director buys = moderate signal
        """
        if signal_data.get('source') != 'form4':
            return 1.0
        
        title = signal_data.get('title', '').lower() if signal_data.get('title') else ''
        
        # CEO/CFO = highest quality
        if 'ceo' in title or 'chief executive' in title:
            return 1.5
        if 'cfo' in title or 'chief financial' in title:
            return 1.4
        
        # President/COO
        if 'president' in title or 'coo' in title:
            return 1.3
        
        # Other C-suite
        if 'chief' in title or 'cto' in title or 'cio' in title:
            return 1.2
        
        # Directors
        if 'director' in title:
            return 1.0
        
        # Other officers
        if 'officer' in title or 'vp' in title or 'vice president' in title:
            return 0.9
        
        # Unknown/other
        return 0.7
    
    def calculate_consensus_score(self, signal_data: dict, similar_signals: list) -> float:
        """
        Check if multiple insiders buying same stock (cluster).
        
        3+ insiders buying = strong consensus = higher score
        """
        if not similar_signals:
            return 0.2  # Base score for no consensus
        
        # Count similar signals (same symbol, same direction)
        cluster_count = len(similar_signals)
        
        # Base score from cluster size
        if cluster_count >= 5:
            base_score = 1.0
        elif cluster_count >= 3:
            base_score = 0.8
        elif cluster_count >= 2:
            base_score = 0.5
        else:
            base_score = 0.2
        
        return base_score

def example_usage():
    """Example of how to use SignalQualityFilter."""
    filter_obj = SignalQualityFilter()
    
    # Test signal data
    test_signals = [
        {
            'source': 'form4',
            'symbol': 'AAPL',
            'price': 150.0,
            'transaction_value': 50000.0,
            'filer_name': 'Tim Cook',
            'title': 'CEO',
            'transaction_code': 'P',
            'filing_date': datetime.utcnow() - timedelta(days=5)
        },
        {
            'source': 'congressional',
            'symbol': 'PENNY',
            'price': 0.50,
            'transaction_value': 1000.0,
            'filer_name': 'Congress Member',
            'filing_date': datetime.utcnow() - timedelta(days=5)
        },
        {
            'source': 'congressional',
            'symbol': 'OLD',
            'price': 100.0,
            'transaction_value': 50000.0,
            'filer_name': 'Congress Member',
            'filing_date': datetime.utcnow() - timedelta(days=45)
        }
    ]
    
    for i, signal in enumerate(test_signals):
        passes, reason = filter_obj.apply_quality_filters(signal)
        recency = filter_obj.calculate_recency_score(signal)
        quality_mult = filter_obj.get_insider_quality_multiplier(signal)
        
        print(f"Signal {i+1}:")
        print(f"  Passes: {passes}")
        print(f"  Reason: {reason}")
        print(f"  Recency: {recency:.3f}")
        print(f"  Quality mult: {quality_mult:.3f}")
        print()

if __name__ == '__main__':
    example_usage()
