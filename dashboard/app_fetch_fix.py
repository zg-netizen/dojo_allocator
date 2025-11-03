# This is the new fetch function to replace the old one

def fetch_benchmark_data(ticker, days):
    """Fetch benchmark data using Alpaca API"""
    import os
    import requests
    import pandas as pd
    from datetime import datetime, timedelta
    
    try:
        API_KEY = os.getenv("ALPACA_API_KEY")
        API_SECRET = os.getenv("ALPACA_API_SECRET")
        
        if not API_KEY:
            return pd.Series()
        
        fetch_days = max(days, 10)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=fetch_days)
        
        url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
        params = {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "timeframe": "1Day"
        }
        headers = {
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": API_SECRET
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return pd.Series()
        
        data = response.json()
        bars = data.get("bars", [])
        
        if not bars:
            return pd.Series()
        
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.set_index("t")
        df = df.sort_index()
        
        if days < fetch_days:
            cutoff = end_date - timedelta(days=days)
            df = df[df.index >= cutoff]
        
        return df["c"]
        
    except Exception as e:
        return pd.Series()
