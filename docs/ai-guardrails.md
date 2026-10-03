# How the AI is kept honest

1. **Numbers come from code, not the model.** `backend/app/analysis/` computes indicators, liquidity, structure, FVGs,
   the signal and the plan. The model only receives that structured context (`analysis["context"]`).
2. **Number guard.** `services/llm.py::unverified_numbers` rejects any LLM answer that states a price-scale number that
   is not in the context or the user's own message. A rejected answer is replaced by the deterministic explainer.
3. **Offline by default.** With no API key the app uses `agents/explanation_agent.py`, a rules-based explainer built on the
   same data. Nothing in the product requires an LLM.
4. **WAIT is a first-class result.** A setup needs every *required* condition. Missing ones are listed, not hidden.
   Chasing is blocked (entry extended from the confirming level) and so is an invalidation that is too far from price.
5. **No probabilities.** Evidence is bucketed as supporting / against / caution / missing.
6. **No data, no analysis.** If candles are unavailable the API returns an error and the copilot says so. Stale or
   closed-market data is flagged on every response (`data_status`).
7. **No orders.** There is no broker, order or account code anywhere. "Paper analysis" only replays saved plans against
   later candles.
