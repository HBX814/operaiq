-- OperaIQ Looker Studio Integration
-- These queries power the real-time operational dashboards in Looker Studio.

-- 1. Incident Resolution Metrics (MTTR)
-- Tracks the Mean Time To Resolution for incidents by service.
SELECT
  service,
  COUNT(*) as total_incidents,
  AVG(TIMESTAMP_DIFF(resolved_timestamp, timestamp, MINUTE)) as mttr_minutes,
  MAX(TIMESTAMP_DIFF(resolved_timestamp, timestamp, MINUTE)) as max_resolution_minutes
FROM `operaiq.events`
WHERE event_type = 'incident'
  AND status = 'resolved'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY service
ORDER BY mttr_minutes DESC;


-- 2. Deployment Success vs Failure Rate
-- Calculates the success and failure rate of deployments per service.
SELECT
  service,
  status,
  COUNT(*) as deployment_count,
  COUNT(*) / SUM(COUNT(*)) OVER(PARTITION BY service) * 100 as percentage
FROM `operaiq.events`
WHERE event_type = 'deployment'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY service, status
ORDER BY service, percentage DESC;


-- 3. AI Remediation Efficacy (Agentic Rollbacks)
-- Measures how often incidents were resolved automatically via the RemediationAgent.
SELECT
  DATE(timestamp) as date,
  COUNT(*) as total_incidents,
  COUNTIF(triggered_by_deployment_id IS NOT NULL) as deployment_related,
  COUNTIF(status = 'resolved' AND resolution_method = 'ai_agent') as ai_resolved_count
FROM `operaiq.events`
WHERE event_type = 'incident'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC;


-- 4. Anomaly Detection (Latency & Error Rates)
-- Highlights services experiencing significant metric deviations from their 7-day baseline.
WITH baseline AS (
  SELECT
    service,
    metric_type,
    AVG(CAST(value AS FLOAT64)) as avg_value,
    STDDEV(CAST(value AS FLOAT64)) as stddev_value
  FROM `operaiq.events`
  WHERE event_type = 'metric'
    AND timestamp BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY) AND TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  GROUP BY service, metric_type
)
SELECT
  e.service,
  e.metric_type,
  e.timestamp,
  e.value,
  b.avg_value,
  (CAST(e.value AS FLOAT64) - b.avg_value) / NULLIF(b.stddev_value, 0) as z_score
FROM `operaiq.events` e
JOIN baseline b ON e.service = b.service AND e.metric_type = b.metric_type
WHERE e.event_type = 'metric'
  AND e.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  AND (CAST(e.value AS FLOAT64) - b.avg_value) / NULLIF(b.stddev_value, 0) > 3.0
ORDER BY z_score DESC;
