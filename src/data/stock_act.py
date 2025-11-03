"""Congressional STOCK Act disclosure fetcher."""
import requests
from datetime import datetime, timedelta
from typing import Dict, List
from src.utils.logging import get_logger
from config.settings import get_data_sources_config

logger = get_logger(__name__)

class StockActFetcher:
    """Fetches congressional stock trading disclosures.
    Data source: House Stock Watcher or similar aggregator."""
    
    def __init__(self):
        config = get_data_sources_config()['stock_act']
        self.base_url = config['base_url']
        self.update_frequency = config['update_frequency_hours']
        self.lookback_days = config['lookback_days']
    
    def fetch_recent_trades(self) -> List[Dict]:
        """Fetch recent congressional stock trades.
        
        Returns:
            List of trade dicts with member, symbol, transaction type, amount range
        """
        logger.info("Fetching congressional trades")
        url = f"{self.base_url}/all_transactions.json"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            all_trades = response.json()
            
            cutoff_date = datetime.utcnow() - timedelta(days=self.lookback_days)
            recent_trades = []
            
            for trade in all_trades:
                try:
                    trade_date_str = trade.get('transaction_date', '')
                    if trade_date_str:
                        trade_date = datetime.fromisoformat(trade_date_str.replace('Z', '+00:00'))
                        if trade_date >= cutoff_date:
                            recent_trades.append(trade)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing trade date: {e}")
                    continue
            
            logger.info(f"Fetched {len(recent_trades)} recent congressional trades")
            return recent_trades
            
        except Exception as e:
            logger.error(f"Failed to fetch congressional trades: {e}")
            return []
    
    def transform_to_signal_format(self, trades: List[Dict]) -> List[Dict]:
        """Transform raw congressional trades into standardized signal format.
        
        Args:
            trades: Raw trade data from House Stock Watcher
            
        Returns:
            List of signal dicts ready for scoring
        """
        signals = []
        
        for trade in trades:
            tx_type = trade.get('type', '').lower()
            if 'purchase' in tx_type or 'buy' in tx_type:
                direction = 'LONG'
            elif 'sale' in tx_type or 'sell' in tx_type:
                direction = 'SHORT'
            else:
                continue
            
            amount_str = trade.get('amount', '')
            transaction_value = self._parse_amount_range(amount_str)
            
            signal = {
                'source': 'stock_act',
                'symbol': trade.get('ticker', '').upper(),
                'direction': direction,
                'filer_name': trade.get('representative', ''),
                'filer_cik': None,
                'transaction_date': trade.get('transaction_date'),
                'filing_date': trade.get('disclosure_date'),
                'transaction_value': transaction_value,
                'raw_data': trade
            }
            signals.append(signal)
        
        return signals
    
    def _parse_amount_range(self, amount_str: str) -> float:
        """Parse amount range string to midpoint value.
        
        Args:
            amount_str: Amount range string (e.g., "$1,001 - $15,000")
            
        Returns:
            Midpoint value as float
        """
        if not amount_str or amount_str == '--':
            return 0.0
        
        amount_str = amount_str.replace('$', '').replace(',', '')
        
        if '-' in amount_str:
            parts = amount_str.split('-')
            try:
                low = float(parts[0].strip())
                high = float(parts[1].strip())
                return (low + high) / 2.0
            except (ValueError, IndexError):
                return 0.0
        else:
            try:
                return float(amount_str)
            except ValueError:
                return 0.0

def example_usage():
    """Example of how to use StockActFetcher."""
    fetcher = StockActFetcher()
    
    trades = fetcher.fetch_recent_trades()
    print(f"Fetched {len(trades)} congressional trades")
    
    signals = fetcher.transform_to_signal_format(trades)
    print(f"Transformed into {len(signals)} signals")
    
    if signals:
        sample = signals[0]
        print(f"\nSample signal:")
        print(f"  Symbol: {sample['symbol']}")
        print(f"  Direction: {sample['direction']}")
        print(f"  Filer: {sample['filer_name']}")
        print(f"  Value: ${sample['transaction_value']:,.2f}")

if __name__ == '__main__':
    example_usage()
