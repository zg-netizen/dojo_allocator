"""Data transformation utilities.
Standardizes raw data from various sources into unified signal format."""
from typing import Dict, List
from datetime import datetime
import hashlib

class SignalTransformer:
    """Transforms raw data from different sources into standardized signal format."""
    
    @staticmethod
    def generate_signal_id(
        source: str,
        symbol: str,
        transaction_date: datetime,
        filer_cik: str = None
    ) -> str:
        """Generate unique signal ID from key attributes.
        
        Args:
            source: Data source (insider, stock_act, etc.)
            symbol: Stock ticker
            transaction_date: When transaction occurred
            filer_cik: Optional filer identifier
            
        Returns:
            Unique signal ID
        """
        components = [
            source,
            symbol.upper(),
            transaction_date.isoformat(),
            filer_cik or ""
        ]
        hash_input = "|".join(components)
        hash_obj = hashlib.sha256(hash_input.encode('utf-8'))
        return f"{source}_{hash_obj.hexdigest()[:16]}"
    
    @staticmethod
    def validate_signal(signal: Dict) -> bool:
        """Validate that signal has all required fields.
        
        Args:
            signal: Signal dict to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = [
            'source', 'symbol', 'direction',
            'transaction_date', 'filing_date'
        ]
        
        for field in required_fields:
            if field not in signal or signal[field] is None:
                return False
        
        symbol = signal.get('symbol', '')
        if not symbol or not symbol.isupper() or len(symbol) > 5:
            return False
        
        if signal.get('direction') not in ['LONG', 'SHORT']:
            return False
        
        return True

class DataValidator:
    """Validates data quality and enforces compliance requirements."""
    
    @staticmethod
    def validate_filing_lag(
        filing_date: datetime,
        transaction_date: datetime,
        max_lag_days: int = 45
    ) -> bool:
        """Ensure filing is recent enough to be actionable.
        
        Args:
            filing_date: When filed
            transaction_date: When transaction occurred
            max_lag_days: Maximum acceptable lag
            
        Returns:
            True if acceptable, False if too stale
        """
        lag = (filing_date - transaction_date).days
        if lag > max_lag_days:
            return False
        return True
    
    @staticmethod
    def validate_symbol(symbol: str) -> bool:
        """Validate ticker symbol format.
        
        Args:
            symbol: Ticker to validate
            
        Returns:
            True if valid format
        """
        if not symbol:
            return False
        
        if not symbol.isupper():
            return False
        
        if len(symbol) < 1 or len(symbol) > 5:
            return False
        
        if not symbol.isalpha():
            return False
        
        return True
    
    @staticmethod
    def validate_transaction_value(
        value: float,
        min_value: float = 1000
    ) -> bool:
        """Ensure transaction is large enough to be meaningful.
        
        Args:
            value: Transaction value in dollars
            min_value: Minimum acceptable value
            
        Returns:
            True if large enough
        """
        if not value or value < min_value:
            return False
        return True

def example_usage():
    """Example of transformation workflow."""
    from datetime import datetime
    
    raw_trade = {
        'representative': 'John Doe',
        'ticker': 'AAPL',
        'transaction_date': '2025-01-10',
        'disclosure_date': '2025-01-12',
        'type': 'purchase',
        'amount': '$15,001 - $50,000'
    }
    
    signal = {
        'source': 'stock_act',
        'symbol': raw_trade['ticker'],
        'direction': 'LONG',
        'filer_name': raw_trade['representative'],
        'transaction_date': datetime.fromisoformat(raw_trade['transaction_date']),
        'filing_date': datetime.fromisoformat(raw_trade['disclosure_date']),
        'transaction_value': 32500.0,
        'raw_data': raw_trade
    }
    
    signal_id = SignalTransformer.generate_signal_id(
        source=signal['source'],
        symbol=signal['symbol'],
        transaction_date=signal['transaction_date']
    )
    signal['signal_id'] = signal_id
    
    print(f"Signal ID: {signal_id}")
    
    is_valid = SignalTransformer.validate_signal(signal)
    print(f"Valid: {is_valid}")
    
    lag_ok = DataValidator.validate_filing_lag(
        filing_date=signal['filing_date'],
        transaction_date=signal['transaction_date']
    )
    print(f"Filing lag acceptable: {lag_ok}")

if __name__ == '__main__':
    example_usage()
