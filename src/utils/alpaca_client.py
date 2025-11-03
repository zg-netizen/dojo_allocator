"""Simple Alpaca API client using requests."""
import os
import requests
from decimal import Decimal
from typing import Dict

def get_account():
    """Get account info."""
    key = os.getenv('ALPACA_API_KEY')
    secret = os.getenv('ALPACA_API_SECRET')
    
    headers = {
        'APCA-API-KEY-ID': key,
        'APCA-API-SECRET-KEY': secret
    }
    
    r = requests.get('https://paper-api.alpaca.markets/v2/account', headers=headers)
    r.raise_for_status()
    return r.json()

def get_quote(symbol: str) -> Dict[str, Decimal]:
    """Get latest quote."""
    key = os.getenv('ALPACA_API_KEY')
    secret = os.getenv('ALPACA_API_SECRET')
    
    headers = {
        'APCA-API-KEY-ID': key,
        'APCA-API-SECRET-KEY': secret
    }
    
    r = requests.get(f'https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest', headers=headers)
    r.raise_for_status()
    data = r.json()
    
    quote = data['quote']
    return {
        'bid': Decimal(str(quote['bp'])),
        'ask': Decimal(str(quote['ap'])),
        'last': Decimal(str((quote['bp'] + quote['ap']) / 2)),
        'volume': Decimal(0)
    }
