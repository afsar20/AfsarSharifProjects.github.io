# Quantitative strategist research — decision brief

## Trading Performance Diagnostics

- Question: is weaker net trading performance caused by execution or signal deterioration?
- Experiment: 100,000 synthetic parent orders and 289,839 clean child fills; 61 held-out sessions.
- Accounting: maximum cost-bridge error $9.73e-10; retries are idempotent, invalid messages quarantined, conflicting IDs and overfills fail.
- Findings: independent simulated routing and signal-decay episodes are separated by cost residuals, latency and forecast errors. Classification tables and weaker-effect challenge cases are included.
- Decision: investigate execution routing separately from signal calibration. Venue comparisons remain descriptive.
- Limit: this validates a transparent simulator and accounting/monitoring implementation, not a live market result.

## Portfolio Risk and Crowding Lab

- Question: do different books share risk, and what changes when capital is reallocated?
- Inputs: real French industry and five-factor daily returns, 2015–2025; six disclosed illustrative books; 2020–2025 walk-forward evaluation.
- Equal allocation: 9.24% annualised return, 8.28% annual volatility, -11.63% maximum drawdown.
- Minimum variance: 5.94% annualised return, 3.89% annual volatility, -4.64% maximum drawdown.
- Decision: allocation changes risk and realised return together; investigate factor exposures, risk contributions and tail exceptions before changing the risk budget.
- Limit: revised public indices and illustrative books/costs, not directly tradable assets or genuine fund performance. No alpha or capacity claim.

## Role relevance

These projects demonstrate trading-data analytics, daily risk tools, strategic deep dives, continuous monitoring and communication of methods and results. They are independently designed portfolio work, with no QRT data or affiliation.
