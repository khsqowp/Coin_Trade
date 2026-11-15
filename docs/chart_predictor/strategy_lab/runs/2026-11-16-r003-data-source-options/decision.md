# R003 decision

Decision: `no_performance_test_until_source_and_evaluation_gates_pass`; no metrics, no pass, and zero qualifying strategies.

The source investigation made concrete progress but did not remove the source gate:

- KR has an official daily stock/ETF API back to 2010 under authenticated, non-commercial, non-third-party terms. It is a plausible route only if the user chooses to register/accept the terms; the API docs do not prove complete delisted/PIT universe or adjustment history.
- US has credible licensed historical routes (CRSP and TAQ), but neither is established as already licensed by the user. Nasdaq's publicly visible page is not a bulk capture grant, and SEC filing APIs are not OHLC data.
- Binance Vision explicitly permits personal non-production historical backtesting within its terms; it does not clearly answer whether private/manual live decisions informed by derived data are allowed. Official public streams can technically support a future observation period, but connection docs do not resolve the data-use question or historical contract/funding completeness.

The prior KR/US and crypto performance runs remain exploratory/rejected or data-blocked as recorded in their own reports. Their exposed histories are not to be re-tuned. The adversarial reviewer correctly notes that uncertainty about rights is not proof of illegality, while lack of verified rights is enough to withhold a new performance claim.

Next decision gate: select a per-market source path and authorize only the needed user-controlled action (e.g. account/key setup or considering a paid quote). Do not ask the agent to create an account, accept terms, contact a provider, download data, or start a new strategy grid before that gate. For crypto forward evaluation, freeze the target-first protocol and blind independent agent outputs before collecting outcomes.
