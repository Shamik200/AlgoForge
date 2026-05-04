"""External data source integrations for fundamental analysis (Phase 12).

Integrates with SEC EDGAR for US equities and CoinGecko for crypto fundamentals.
"""

import logging
from typing import Any
import httpx

from algoforge.fundamental.models import FinancialMetrics

logger = logging.getLogger(__name__)


class SECDataSource:
    """Fetches fundamental data from SEC EDGAR."""
    
    BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"
    
    def __init__(self, user_agent: str = "AlgoForge/1.0 (contact@algoforge.com)"):
        self.headers = {"User-Agent": user_agent}
        
    async def fetch_financials(self, cik: str, symbol: str) -> FinancialMetrics:
        """Fetch latest financials for a given CIK and return mapped metrics."""
        # Note: SEC EDGAR requires zero-padded 10-digit CIKs
        padded_cik = str(cik).zfill(10)
        url = f"{self.BASE_URL}/CIK{padded_cik}.json"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_edgar_facts(symbol, data)
                else:
                    logger.warning(f"SEC API returned {response.status_code} for {symbol}")
        except Exception as e:
            logger.error(f"Error fetching SEC data for {symbol}: {e}")
            
        return FinancialMetrics(symbol=symbol)

    def _parse_edgar_facts(self, symbol: str, data: dict[str, Any]) -> FinancialMetrics:
        """Extract key GAAP metrics from SEC XBRL facts (simplified)."""
        metrics = FinancialMetrics(symbol=symbol)
        try:
            us_gaap = data.get("facts", {}).get("us-gaap", {})
            
            # Extract Revenue / Net Income / Assets (simplified grabbing latest values)
            # In a real impl, we would traverse the 'units' -> 'USD' arrays to get the latest 10-K/10-Q value.
            if "NetIncomeLoss" in us_gaap:
                metrics.roe = 0.15  # Placeholder for parsed calculation
            if "Assets" in us_gaap:
                metrics.current_ratio = 1.5
            if "Liabilities" in us_gaap:
                metrics.debt_to_equity = 0.8
                
        except Exception as e:
            logger.warning(f"Error parsing SEC data for {symbol}: {e}")
            
        return metrics


class CoinGeckoSource:
    """Fetches fundamental data for Crypto assets from CoinGecko."""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    async def fetch_metrics(self, symbol: str) -> FinancialMetrics:
        """Fetch coin data and map to fundamental metrics."""
        # Symbol mapping (e.g., BTC -> bitcoin)
        coin_id = self._map_symbol(symbol)
        if not coin_id:
            return FinancialMetrics(symbol=symbol)
            
        url = f"{self.BASE_URL}/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=true&developer_data=true"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_coingecko(symbol, data)
                elif response.status_code == 429:
                    logger.warning(f"CoinGecko rate limit hit for {symbol}")
        except Exception as e:
            logger.error(f"Error fetching CoinGecko data for {symbol}: {e}")
            
        return FinancialMetrics(symbol=symbol)
        
    def _parse_coingecko(self, symbol: str, data: dict[str, Any]) -> FinancialMetrics:
        """Map crypto fundamentals to standard financial metrics proxy."""
        metrics = FinancialMetrics(symbol=symbol)
        
        market_data = data.get("market_data", {})
        community_data = data.get("community_data", {})
        dev_data = data.get("developer_data", {})
        
        # Proxies
        # PE Ratio -> MktCap / Fully Diluted Valuation (Valuation proxy)
        mcap = market_data.get("market_cap", {}).get("usd", 0)
        fdv = market_data.get("fully_diluted_valuation", {}).get("usd", 0)
        if fdv and mcap:
            metrics.pe_ratio = fdv / mcap  # Not real PE, but a valuation ratio
            
        # Growth -> 30d price change as growth proxy
        price_change_30d = market_data.get("price_change_percentage_30d", 0)
        if price_change_30d:
            metrics.revenue_growth_yoy = price_change_30d / 100.0
            
        # Quality -> Community / Dev score mapped to FCF/Quality
        dev_score = data.get("developer_score", 0)
        metrics.free_cash_flow = dev_score  # Higher dev score = higher quality
        
        # Margin -> Liquidity proxy
        metrics.net_margin = 0.20 if mcap > 1_000_000_000 else 0.05
        
        return metrics

    def _map_symbol(self, symbol: str) -> str:
        """Map standard symbols to CoinGecko IDs."""
        mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "XRP": "ripple",
        }
        return mapping.get(symbol.split("/")[0].upper())
