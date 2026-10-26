-- Portable SQLite analytical layer. Positive shortfall means worse execution.
-- The clean fill table has a unique fill_id. Parent orders have a unique order_id.
-- An unfilled order stays in the result through the LEFT JOIN.
DROP VIEW IF EXISTS order_diagnostics;
CREATE VIEW order_diagnostics AS
WITH fills_by_order AS (
 SELECT order_id, SUM(qty) AS filled_qty, SUM(qty * price) AS traded_value,
        SUM(fee) AS fees, SUM(qty * latency_ms) / SUM(qty) AS latency_ms
 FROM fills GROUP BY order_id
), joined AS (
 SELECT o.*, COALESCE(f.filled_qty,0) AS filled_qty,
        COALESCE(f.traded_value,0) AS traded_value, COALESCE(f.fees,0) AS fees,
        COALESCE(f.latency_ms,0) AS latency_ms,
        o.qty * o.decision_price AS decision_notional
 FROM orders o LEFT JOIN fills_by_order f USING(order_id)
)
SELECT *,
 side * filled_qty * (arrival_price - decision_price) AS delay_usd,
 side * filled_qty * (benchmark_price - arrival_price) AS market_usd,
 side * (traded_value - filled_qty * benchmark_price) AS execution_usd,
 side * (qty - filled_qty) * (end_price - decision_price) AS opportunity_usd,
 side * (traded_value + (qty - filled_qty) * end_price - qty * decision_price) + fees AS is_usd,
 side * qty * (end_price - decision_price) AS ideal_pnl_usd,
 side * (filled_qty * end_price - traded_value) - fees AS net_pnl_usd,
 CASE WHEN filled_qty > 0 THEN 10000.0 * side *
      (traded_value / filled_qty - benchmark_price) / decision_price ELSE NULL END AS execution_bps
FROM joined;

DROP VIEW IF EXISTS daily_production;
CREATE VIEW daily_production AS
SELECT date, COUNT(*) AS orders, SUM(decision_notional) AS decision_notional,
       SUM(filled_qty * decision_price) / SUM(decision_notional) AS fill_rate,
       SUM(is_usd) AS shortfall_usd, SUM(net_pnl_usd) AS net_pnl_usd,
       10000.0 * SUM(is_usd) / SUM(decision_notional) AS shortfall_bps,
       10000.0 * SUM(delay_usd) / SUM(decision_notional) AS delay_bps,
       10000.0 * SUM(market_usd) / SUM(decision_notional) AS market_bps,
       10000.0 * SUM(execution_usd) / SUM(decision_notional) AS execution_bps,
       10000.0 * SUM(opportunity_usd) / SUM(decision_notional) AS opportunity_bps,
       10000.0 * SUM(fees) / SUM(decision_notional) AS fee_bps
FROM order_diagnostics GROUP BY date;
