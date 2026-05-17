from algoforge.core.models import Signal, Position

class PromptBuilder:
    """Builds structured prompts for the FinLLMClient."""

    @staticmethod
    def build_fundamental_prompt(symbol: str, data: dict) -> str:
        return f"Analyze {symbol} fundamentals: {data}"

    @staticmethod
    def build_technical_prompt(symbol: str, regime: str, indicators: dict) -> str:
        return f"Analyze {symbol} technicals. Regime is {regime}. Indicators: {indicators}"

    @staticmethod
    def build_signal_prompt(signal: Signal, technical_summary: str) -> str:
        return f"Confirm signal: {signal.direction} on {signal.symbol} at {signal.entry_price}. Technical Context: {technical_summary}"

    @staticmethod
    def build_risk_prompt(portfolio_state: dict, current_signal: Signal) -> str:
        return f"Review risk for adding {current_signal.direction} on {current_signal.symbol}. Portfolio: {portfolio_state}"

    @staticmethod
    def build_thesis_prompt(signal: Signal, confirmation_reasons: list[str]) -> str:
        return f"Generate trade thesis for {signal.symbol} {signal.direction}. Reasons: {confirmation_reasons}"

    @staticmethod
    def build_post_trade_prompt(position: Position) -> str:
        return f"Analyze closed trade on {position.symbol}. PnL: {position.unrealized_pnl}. Entry: {position.entry_price} Exit: {position.current_price}"
