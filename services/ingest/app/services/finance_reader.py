"""FinanceDataReader wrapper — F1.1 시세 파이프라인."""
from datetime import datetime, timedelta

import FinanceDataReader as fdr


class FinanceReaderService:
    def get_price(self, ticker: str) -> dict:
        end = datetime.today()
        start = end - timedelta(days=7)
        df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
        if df.empty:
            raise ValueError(f"No data for ticker: {ticker}")
        last = df.iloc[-1]
        change = float(last["Change"]) if "Change" in df.columns else 0.0
        return {
            "ticker": ticker,
            "price": float(last["Close"]),
            "change": change,
            "change_pct": change,
            "volume": int(last["Volume"]) if "Volume" in df.columns else 0,
            "timestamp": df.index[-1].strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "FinanceDataReader",
        }

    def get_ohlcv(self, ticker: str, days: int = 30) -> list[dict]:
        end = datetime.today()
        start = end - timedelta(days=days)
        df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
        if df.empty:
            return []
        bars = []
        for date, row in df.iterrows():
            bars.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]) if "Volume" in df.columns else 0,
            })
        return bars

    def get_stock_list(self, market: str = "KRX") -> list[dict]:
        try:
            df = fdr.StockListing(market)
        except Exception as exc:
            raise ValueError(f"Cannot list {market}: {exc}") from exc
        if df.empty:
            return []
        name_col = next((c for c in ["Name", "name"] if c in df.columns), None)
        code_col = next((c for c in ["Code", "Symbol", "symbol"] if c in df.columns), None)
        market_col = next((c for c in ["Market", "market"] if c in df.columns), None)
        cols = [c for c in [code_col, name_col, market_col] if c]
        return df[cols].head(100).rename(
            columns={code_col: "code", name_col: "name", market_col: "market"}
        ).to_dict(orient="records")
