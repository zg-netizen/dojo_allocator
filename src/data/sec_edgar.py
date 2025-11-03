"""SEC EDGAR data fetcher for insider transactions and 13F filings."""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from src.utils.logging import get_logger
from config.settings import get_data_sources_config

logger = get_logger(__name__)

class SECEdgarFetcher:
    """Fetches insider transactions (Form 4) and institutional holdings (Form 13F) from SEC EDGAR.
    Rate limit: 10 requests/second per SEC guidelines."""
    
    def __init__(self):
        config = get_data_sources_config()['sec_edgar']
        self.base_url = config['base_url']
        self.user_agent = config['user_agent']
        self.rate_limit = config['rate_limit_requests_per_second']
        self.lookback_days = config['lookback_days']
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov'
        })
        self._last_request_time = 0
    
    def _rate_limit_delay(self):
        """Enforce rate limit between requests."""
        elapsed = time.time() - self._last_request_time
        min_delay = 1.0 / self.rate_limit
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
        self._last_request_time = time.time()
    
    def fetch_recent_form4(self, limit: int = 100) -> List[Dict]:
        """Fetch recent Form 4 (insider transaction) filings.
        
        Args:
            limit: Maximum number of filings to return
            
        Returns:
            List of insider transaction dicts
            
        Note: Using OpenInsider as reliable source for insider trades
        since SEC EDGAR RSS feed doesn't consistently have Form 4 filings.
        """
        logger.info("Fetching Form 4 filings via OpenInsider", limit=limit)
        
        try:
            # Use OpenInsider as a reliable source for insider trades
            from src.data.openinsider import OpenInsiderFetcher
            
            oi_fetcher = OpenInsiderFetcher()
            
            # Fetch recent insider purchases (these are Form 4 equivalent)
            insider_trades = oi_fetcher.fetch_recent_buys(limit=limit)
            
            # Transform to Form 4 format
            form4_filings = []
            
            for trade in insider_trades:
                # Skip sales (only keep purchases)
                if 'Sale' in trade.get('trade_type', ''):
                    continue
                
                # Skip if no transaction value or negative value (sales)
                if not trade.get('value', 0) or trade.get('value', 0) < 0:
                    continue
                
                filing = {
                    'accession_number': f"oi_{trade.get('filing_date', '')}_{trade.get('ticker', '')}",
                    'company_name': trade.get('ticker', ''),
                    'insider_name': trade.get('insider_name', ''),
                    'ticker': trade.get('ticker', ''),
                    'filing_date': trade.get('filing_date', ''),
                    'filing_url': f"https://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1",
                    'form_type': '4',
                    'transaction_code': 'P',  # Purchase
                    'transaction_date': trade.get('trade_date', ''),
                    'shares': trade.get('qty', 0),
                    'price': trade.get('price', 0),
                    'transaction_value': trade.get('value', 0),
                    'raw_title': f"Form 4 - {trade.get('ticker', '')} {trade.get('insider_name', '')}"
                }
                
                form4_filings.append(filing)
            
            logger.info(f"Fetched {len(form4_filings)} Form 4 equivalent filings via OpenInsider")
            return form4_filings
            
        except Exception as e:
            logger.error(f"Failed to fetch Form 4 filings: {e}")
            return []
    
    def _extract_ticker_from_url(self, filing_url: str) -> str:
        """Extract company ticker from SEC filing URL."""
        try:
            # URL format: https://www.sec.gov/Archives/edgar/data/[CIK]/[accession]/[filename]
            parts = filing_url.split('/')
            if len(parts) > 6:
                cik = parts[6]
                # We'd need a CIK to ticker mapping, for now return empty
                return ""
            return ""
        except:
            return ""
    
    def _extract_accession_number(self, filing_url: str) -> str:
        """Extract accession number from filing URL."""
        try:
            parts = filing_url.split('/')
            if len(parts) > 7:
                return parts[7]
            return ""
        except:
            return ""
    
    def _fetch_form4_transaction_details(self, filing_url: str) -> Dict:
        """Fetch detailed transaction data from Form 4 filing."""
        try:
            self._rate_limit_delay()
            response = self.session.get(filing_url, timeout=30)
            response.raise_for_status()
            
            # Parse the filing document for transaction details
            # This is a simplified parser - production would use more sophisticated XML parsing
            content = response.text
            
            # Extract transaction details using regex patterns
            import re
            
            transaction_data = {}
            
            # Look for transaction type (P for purchase, S for sale)
            transaction_type_match = re.search(r'<transactionCode>([PS])</transactionCode>', content)
            if transaction_type_match:
                transaction_data['transaction_code'] = transaction_type_match.group(1)
            
            # Look for transaction date
            date_match = re.search(r'<transactionDate>(\d{4}-\d{2}-\d{2})</transactionDate>', content)
            if date_match:
                transaction_data['transaction_date'] = date_match.group(1)
            
            # Look for shares
            shares_match = re.search(r'<transactionShares>([0-9,]+)</transactionShares>', content)
            if shares_match:
                shares_str = shares_match.group(1).replace(',', '')
                transaction_data['shares'] = int(shares_str)
            
            # Look for price
            price_match = re.search(r'<transactionPricePerShare>([0-9.]+)</transactionPricePerShare>', content)
            if price_match:
                transaction_data['price'] = float(price_match.group(1))
            
            # Calculate transaction value
            if 'shares' in transaction_data and 'price' in transaction_data:
                transaction_data['transaction_value'] = transaction_data['shares'] * transaction_data['price']
            
            return transaction_data
            
        except Exception as e:
            logger.warning(f"Failed to fetch transaction details from {filing_url}: {e}")
            return {}
    
    def transform_form4_to_signal_format(self, filings: List[Dict]) -> List[Dict]:
        """Transform Form 4 filings into standardized signal format.
        
        Args:
            filings: Raw Form 4 filing data
            
        Returns:
            List of signal dicts ready for scoring
        """
        signals = []
        
        for filing in filings:
            try:
                # Only process purchases (transaction_code = 'P')
                if filing.get('transaction_code') != 'P':
                    continue
                
                # Skip if no transaction value
                if not filing.get('transaction_value', 0):
                    continue
                
                # Parse filing date
                filing_date = filing.get('filing_date', '')
                if filing_date:
                    try:
                        # Parse ISO format date
                        from datetime import datetime
                        filing_date = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))
                    except:
                        filing_date = None
                
                # Parse transaction date
                transaction_date = filing.get('transaction_date')
                if transaction_date:
                    try:
                        from datetime import datetime
                        transaction_date = datetime.strptime(transaction_date, '%Y-%m-%d')
                    except:
                        transaction_date = None
                
                signal = {
                    'source': 'form4',
                    'symbol': filing.get('ticker', '').upper(),
                    'direction': 'LONG',  # Form 4 purchases are always long
                    'filer_name': filing.get('insider_name', ''),
                    'filer_cik': None,  # Would need CIK mapping
                    'transaction_date': transaction_date,
                    'filing_date': filing_date,
                    'transaction_value': filing.get('transaction_value', 0),
                    'shares': filing.get('shares', 0),
                    'price': filing.get('price', 0),
                    'form_type': '4',
                    'raw_data': filing
                }
                
                signals.append(signal)
                
            except Exception as e:
                logger.warning(f"Error transforming Form 4 filing: {e}")
                continue
        
        return signals
    
    def fetch_recent_13f(self, limit: int = 50) -> List[Dict]:
        """Fetch recent 13F (institutional holdings) filings.
        
        Args:
            limit: Maximum number of filings to return
            
        Returns:
            List of 13F filing summaries
            
        Note: Placeholder implementation - returns empty list.
        Compare quarter-over-quarter to find new positions.
        """
        logger.info("Fetching 13F filings", limit=limit)
        logger.warning("13F fetching not yet implemented - returning empty list")
        return []

def example_usage():
    """Example of how to use SECEdgarFetcher."""
    fetcher = SECEdgarFetcher()
    
    # Fetch Form 4 filings
    form4_filings = fetcher.fetch_recent_form4(limit=10)
    print(f"Fetched {len(form4_filings)} Form 4 filings")
    
    # Fetch 13F filings
    form13f_filings = fetcher.fetch_recent_13f(limit=10)
    print(f"Fetched {len(form13f_filings)} 13F filings")

if __name__ == '__main__':
    example_usage()
