"""Connector Factory.

Instantiates the correct exchange connector based on configuration.
"""

from algoforge.connectors.base import ConnectorBase
from algoforge.connectors.paper import PaperConnector
from algoforge.execution.paper import PaperTradingEngine

class ConnectorFactory:
    """Factory for creating exchange connectors."""

    @staticmethod
    def create(mode: str, **kwargs) -> ConnectorBase:
        """Create a connector.

        Args:
            mode: "paper" or "binance_live"
            **kwargs: Engine parameters (e.g. paper_engine)
        """
        if mode == "paper":
            engine = kwargs.get("paper_engine")
            if not engine:
                raise ValueError("paper_engine is required for paper mode")
            return PaperConnector(engine)
        elif mode == "binance_live":
            # For Phase 13 testing, we will mock the live connector using another paper instance
            # In a real system, this would instantiate BinanceLiveConnector
            engine = kwargs.get("paper_engine")
            return PaperConnector(engine)
        elif mode == "shadow":
            # Phase 13: Paper-Live Reconciliation Engine
            from algoforge.connectors.shadow import ShadowConnector
            
            paper_engine = kwargs.get("paper_engine")
            live_engine = kwargs.get("live_engine")  # Or create a mocked live connector
            if not paper_engine:
                raise ValueError("paper_engine required for shadow mode")
                
            live_connector = PaperConnector(live_engine) if live_engine else PaperConnector(paper_engine)
            paper_connector = PaperConnector(paper_engine)
            
            return ShadowConnector(live_connector, paper_connector)
        else:
            raise ValueError(f"Unknown connector mode: {mode}")
