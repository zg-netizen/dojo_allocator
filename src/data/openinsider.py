"""
OpenInsider.com data fetcher for insider transactions.
Free alternative to SEC EDGAR direct parsing.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Dict, List
from src.utils.logging import get_logger

logger = get_logger(__name__)

class OpenInsiderFetcher:
    """
    Fetches insider transactions from OpenInsider.com.
    Free, no API key needed, web scraping.
    """
    
    def __init__(self):
        self.base_url = "http://openinsider.com"
        # Congressional trades screener URL
        self.congress_url = "http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'Accept': 'text/html'
        })
    
    def fetch_congressional_trades(self, limit: int = 100) -> List[Dict]:
        """
        Fetch congressional trades using OpenInsider screener.
        
        Args:
            limit: Maximum number of transactions
            
        Returns:
            List of congressional transaction dicts
        """
        logger.info("Fetching congressional trades from OpenInsider")
        
        try:
            response = self.session.get(self.congress_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the main data table
            table = soup.find('table', {'class': 'tinytable'})
            if not table:
                logger.warning("No data table found")
                return []
            
            transactions = []
            rows = table.find_all('tr')[1:]  # Skip header
            
            for row in rows[:limit]:
                cols = row.find_all('td')
                if len(cols) < 12:
                    continue
                
                try:
                    transaction = {
                        'filing_date': cols[1].text.strip(),
                        'trade_date': cols[2].text.strip(),
                        'ticker': cols[3].text.strip(),
                        'insider_name': cols[4].text.strip(),
                        'title': cols[5].text.strip(),
                        'trade_type': cols[6].text.strip(),
                        'price': self._parse_price(cols[7].text.strip()),
                        'qty': self._parse_qty(cols[8].text.strip()),
                        'owned': self._parse_qty(cols[9].text.strip()),
                        'value': self._parse_value(cols[11].text.strip())
                    }
                    
                    transactions.append(transaction)
                        
                except Exception as e:
                    logger.warning(f"Error parsing row: {e}")
                    continue
            
            logger.info(f"Fetched {len(transactions)} congressional trades")
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to fetch from OpenInsider: {e}")
            return []
    
    def fetch_recent_buys(self, limit: int = 100) -> List[Dict]:
        """
        Fetch recent insider purchases.
        
        Args:
            limit: Maximum number of transactions
            
        Returns:
            List of insider transaction dicts
        """
        logger.info("Fetching insider buys from OpenInsider")
        
        url = f"{self.base_url}/latest-purchases"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the main data table
            table = soup.find('table', {'class': 'tinytable'})
            if not table:
                logger.warning("No data table found")
                return []
            
            transactions = []
            rows = table.find_all('tr')[1:]  # Skip header
            
            for row in rows[:limit]:
                cols = row.find_all('td')
                if len(cols) < 12:
                    continue
                
                try:
                    transaction = {
                        'filing_date': cols[1].text.strip(),
                        'trade_date': cols[2].text.strip(),
                        'ticker': cols[3].text.strip(),
                        'insider_name': cols[5].text.strip(),  # Fixed column index
                        'title': cols[6].text.strip(),        # Fixed column index
                        'trade_type': cols[7].text.strip(),    # Fixed column index
                        'price': self._parse_price(cols[8].text.strip()),  # Fixed column index
                        'qty': self._parse_qty(cols[9].text.strip()),      # Fixed column index
                        'owned': self._parse_qty(cols[10].text.strip()),    # Fixed column index
                        'value': self._parse_value(cols[12].text.strip())  # Fixed column index
                    }
                    
                    # Keep both purchases and sales (we'll filter later)
                    transactions.append(transaction)
                        
                except Exception as e:
                    logger.warning(f"Error parsing row: {e}")
                    continue
            
            logger.info(f"Fetched {len(transactions)} insider purchases")
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to fetch from OpenInsider: {e}")
            return []
    
    def _parse_price(self, text: str) -> float:
        """Parse price string to float."""
        try:
            return float(text.replace('$', '').replace(',', ''))
        except:
            return 0.0
    
    def _parse_qty(self, text: str) -> int:
        """Parse quantity string to int."""
        try:
            # Handle formats like "+1,000" or "1,000"
            clean = text.replace('+', '').replace(',', '').strip()
            return int(clean)
        except:
            return 0
    
    def _parse_value(self, text: str) -> float:
        """Parse value string to float."""
        try:
            # Handle formats like "$100,000" or "$1,000,000"
            clean = text.replace('$', '').replace(',', '').strip()
            return float(clean)
        except:
            return 0.0
    
    def transform_to_signal_format(self, transactions: List[Dict], source: str = 'congressional', filter_sales: bool = True) -> List[Dict]:
        """
        Transform raw OpenInsider data to standardized signal format.
        
        Args:
            transactions: Raw transaction data
            source: Source label for signals ('congressional', 'insider', or 'form4')
            filter_sales: If True, only keep purchases (filter out sales)
            
        Returns:
            List of signal dicts ready for scoring
        """
        signals = []
        
        for txn in transactions:
            try:
                # Skip sales if filter_sales is True
                if filter_sales and 'Sale' in txn.get('trade_type', ''):
                    continue
                
                # Parse dates - handle both date and datetime formats
                filing_date_str = txn['filing_date'].split()[0]  # Take only date part
                trade_date_str = txn['trade_date'].split()[0]
                filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d')
                trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d')
                
                # Determine direction from trade type (after filtering, should only be purchases)
                if 'S - Sale' in txn.get('trade_type', ''):
                    direction = 'SHORT'
                else:
                    direction = 'LONG'
                
                signal = {
                    'source': source,  # Use provided source instead of hardcoded 'congressional'
                    'symbol': txn['ticker'].upper(),
                    'direction': direction,
                    'filer_name': txn['insider_name'],
                    'filer_cik': None,
                    'transaction_date': trade_date,
                    'filing_date': filing_date,
                    'transaction_value': txn['value'],
                    'shares': txn['qty'],
                    'price': txn['price'],
                    'raw_data': txn
                }
                
                signals.append(signal)
                
            except Exception as e:
                logger.warning(f"Error transforming transaction: {e}")
                continue
        
        return signals


def example_usage():
    """Example of how to use OpenInsiderFetcher."""
    fetcher = OpenInsiderFetcher()
    
    # Fetch congressional trades
    print("=== Congressional Trades ===")
    congress_txns = fetcher.fetch_congressional_trades(limit=20)
    print(f"Fetched {len(congress_txns)} congressional trades")
    
    congress_signals = fetcher.transform_to_signal_format(congress_txns)
    print(f"Transformed into {len(congress_signals)} signals")
    
    if congress_signals:
        sample = congress_signals[0]
        print(f"\nSample congressional signal:")
        print(f"  Symbol: {sample['symbol']}")
        print(f"  Member: {sample['filer_name']}")
        print(f"  Direction: {sample['direction']}")
        print(f"  Value: ${sample['transaction_value']:,.0f}")
    
    # Fetch insider purchases
    print("\n=== Insider Purchases ===")
    insider_txns = fetcher.fetch_recent_buys(limit=20)
    print(f"Fetched {len(insider_txns)} insider purchases")
    
    insider_signals = fetcher.transform_to_signal_format(insider_txns)
    print(f"Transformed into {len(insider_signals)} signals")
    
    if insider_signals:
        sample = insider_signals[0]
        print(f"\nSample insider signal:")
        print(f"  Symbol: {sample['symbol']}")
        print(f"  Insider: {sample['filer_name']}")
        print(f"  Value: ${sample['transaction_value']:,.0f}")


if __name__ == '__main__':
    example_usage()

