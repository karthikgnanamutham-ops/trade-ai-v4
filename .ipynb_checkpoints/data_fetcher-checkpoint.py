import requests, pandas as pd, os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

URL = "https://api.dhan.co/v2/charts/intraday"
TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

def get_ohlc(security_id, interval=5):
    payload = {
        "securityId": str(security_id),
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",
        "interval": interval,
        "fromDate": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "toDate": datetime.now().strftime("%Y-%m-%d")
    }

    r = requests.post(URL, json=payload, headers={"access-token": TOKEN})
    d = r.json()

    if not d or "close" not in d:
        return pd.DataFrame()

    return pd.DataFrame({
        "open": d["open"],
        "high": d["high"],
        "low": d["low"],
        "close": d["close"],
        "volume": d["volume"]
    })
