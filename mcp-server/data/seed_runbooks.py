"""
Runbook Seeder for OperaIQ.
Embeds 10 realistic runbook documents into ChromaDB using sentence-transformers.

Run once before starting the MCP server:
  python data/seed_runbooks.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils import embedding_functions

CHROMADB_PERSIST_DIR = os.environ.get("CHROMADB_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = "runbooks"

RUNBOOKS = [
    {
        "id": "rb-001",
        "service": "payments",
        "title": "Payments Service: High Error Rate Runbook",
        "content": """
# Payments Service High Error Rate Runbook

## Trigger Conditions
- Error rate > 5% sustained for 5+ minutes
- P99 latency > 2000ms

## Immediate Steps (First 5 minutes)
Step 1: Check recent deployments in the payments service.
  - Review deployment history in OperaIQ dashboard
  - If a deployment occurred within the last 30 minutes, initiate rollback immediately
  
Step 2: Verify downstream dependencies.
  - Check Stripe API status at https://status.stripe.com
  - Verify database connection pool health (target: <80% utilization)
  - Check Redis cache hit rate (target: >90%)

Step 3: Examine error logs.
  - Filter for 5xx errors in Cloud Logging
  - Look for patterns: timeout, connection refused, authentication failure
  - Check for correlation with specific payment methods (credit/debit/ACH)

## Escalation
- If error rate > 20%: page on-call SRE immediately
- If Stripe dependency confirmed: notify payments team lead

## Rollback Procedure
1. Use OperaIQ trigger_rollback tool with deployment_id from Step 1
2. Verify rollback completes within 120 seconds
3. Monitor error rate for 10 minutes post-rollback

## Post-Incident
- Create post-mortem within 24 hours
- Review payment retry logic for improvement opportunities
        """,
        "last_updated": "2024-03-15",
    },
    {
        "id": "rb-002",
        "service": "auth",
        "title": "Auth Service: Authentication Failures Runbook",
        "content": """
# Auth Service Authentication Failure Runbook

## Trigger Conditions
- Login failure rate > 10%
- JWT validation errors spiking
- OAuth2 token refresh failures

## Immediate Steps
Step 1: Check OAuth provider status.
  - Google Identity Platform: https://status.cloud.google.com
  - Verify client credentials are not expired

Step 2: Inspect auth service logs.
  - Look for: JWKS fetch failures, certificate expiry, rate limit hits
  - Check token blacklist DB connectivity

Step 3: Validate configuration.
  - Confirm GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars are set
  - Verify redirect URIs match production configuration

Step 4: Check for account lockouts.
  - Excessive failed logins may trigger security lockouts
  - Use admin console to review blocked IPs

## Circuit Breaker
- If >50% of auth requests failing: activate read-only mode
- Notify users via status page

## Recovery
- Restart auth service pods if JWT validation cache is corrupted
- Flush Redis token cache if stale tokens are causing issues
        """,
        "last_updated": "2024-02-20",
    },
    {
        "id": "rb-003",
        "service": "inventory",
        "title": "Inventory Service: Sync Failure Runbook",
        "content": """
# Inventory Sync Failure Runbook

## Trigger Conditions
- Inventory sync job failure alerts
- Stock discrepancies > 0.1%
- Warehouse API timeouts

## Immediate Steps
Step 1: Check warehouse API connectivity.
  - Ping warehouse endpoint (expect <200ms RTT)
  - Review API quota consumption
  - Verify VPN/private network connectivity

Step 2: Check sync job status.
  - Review Cloud Scheduler job logs
  - Look for: connection timeouts, schema mismatches, auth failures

Step 3: Validate data integrity.
  - Run inventory reconciliation query in BigQuery
  - Compare last-known-good snapshot to current state

Step 4: Manual sync trigger.
  - If automated sync is stuck: trigger manual reconciliation
  - Use admin API: POST /api/v1/inventory/sync/force

## Database Issues
- If PostgreSQL replica lag > 30s: switch reads to primary
- If deadlocks detected: kill long-running transactions

## Communication
- Notify warehouse ops team if sync has been failing > 15 minutes
- Update order management system to hold new orders during sync
        """,
        "last_updated": "2024-01-10",
    },
    {
        "id": "rb-004",
        "service": "notifications",
        "title": "Notifications Service: Message Queue Backup Runbook",
        "content": """
# Notifications Pipeline Backup Runbook

## Trigger Conditions
- Pub/Sub subscription backlog > 100k messages
- Email/SMS delivery failures > 5%
- Notification latency > 60 seconds

## Immediate Steps
Step 1: Assess queue depth.
  - Check Pub/Sub metrics in Cloud Console
  - Identify which notification types are backed up (email, SMS, push)

Step 2: Check downstream providers.
  - SendGrid API status: https://status.sendgrid.com
  - Twilio status: https://status.twilio.com
  - Firebase Cloud Messaging status

Step 3: Scale notification workers.
  - Increase Cloud Run instance count if CPU is the bottleneck
  - Review concurrency settings (target: 80 concurrent requests per instance)

Step 4: Apply backpressure.
  - Temporarily disable low-priority notifications (marketing, recommendations)
  - Prioritize transactional notifications (order confirmations, auth codes)

## Message Replay
- For failed messages: use dead letter topic to requeue
- Maximum replay attempts: 5
- Exponential backoff: 1s, 2s, 4s, 8s, 16s

## Provider Failover
- Email: SendGrid → Mailgun failover
- SMS: Twilio → AWS SNS failover
        """,
        "last_updated": "2024-03-01",
    },
    {
        "id": "rb-005",
        "service": "search",
        "title": "Search Service: Index Failure Runbook",
        "content": """
# Search Index Failure Runbook

## Trigger Conditions
- Search API error rate > 3%
- Query latency P99 > 1000ms
- Index freshness > 15 minutes stale

## Immediate Steps
Step 1: Check Elasticsearch/Vertex AI Search cluster health.
  - Verify cluster status is GREEN (not RED/YELLOW)
  - Check disk usage (trigger: >80%)
  - Review JVM heap usage (trigger: >85%)

Step 2: Diagnose slow queries.
  - Use slow query log to identify problematic search patterns
  - Check for missing index aliases
  - Review recent mapping changes

Step 3: Index refresh.
  - If index is stale: trigger manual re-index for affected collections
  - Priority order: products, categories, articles, users

Step 4: Cache warming.
  - Warm search cache for top-100 queries after index recovery
  - Use pre-computed query results for popular searches

## Rollback
- Revert to last known good index snapshot if corruption detected
- Index restoration typically takes 10-30 minutes

## Degraded Mode
- If search is unavailable: serve cached results from CDN
- Show "Search is temporarily degraded" banner to users
        """,
        "last_updated": "2024-02-14",
    },
    {
        "id": "rb-006",
        "service": "payments",
        "title": "Payments Service: Database Connection Pool Exhaustion",
        "content": """
# Payment DB Connection Pool Exhaustion Runbook

## Trigger Conditions
- "connection pool exhausted" errors in logs
- DB connection wait time > 500ms
- Active connections approaching max_connections limit

## Root Causes (common)
1. Long-running transactions not being committed/rolled back
2. Connection leaks in application code
3. Sudden traffic spike without pool scaling
4. Slow queries blocking other connections

## Immediate Steps
Step 1: Check current connection count.
  SELECT count(*) FROM pg_stat_activity WHERE state != 'idle';
  
Step 2: Identify long-running queries.
  SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
  FROM pg_stat_activity 
  WHERE query_start < now() - interval '5 minutes';

Step 3: Kill blocking connections if safe.
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
  WHERE duration > interval '10 minutes' AND state = 'idle in transaction';

Step 4: Increase pool size temporarily.
  - Update Cloud SQL flags: max_connections = current * 1.5
  - Update application PgBouncer config

## Permanent Fix
- Audit connection handling in payment service code
- Add connection pool monitoring alerts at 80% threshold
- Implement query timeout of 30 seconds
        """,
        "last_updated": "2024-03-20",
    },
    {
        "id": "rb-007",
        "service": "auth",
        "title": "Auth Service: Token Refresh Rate Limit Runbook",
        "content": """
# Auth Token Refresh Rate Limit Runbook

## Trigger Conditions
- OAuth token refresh 429 errors appearing in logs
- User authentication failures due to expired tokens
- Third-party provider rate limit headers detected

## Google OAuth Rate Limits
- Per-user token refresh: 50 requests per hour (Google default)
- If exceeding: implement exponential backoff

## Immediate Steps
Step 1: Identify which users are hitting rate limits.
  - Query logs for caller_id with most 429 responses
  - Look for automated processes refreshing tokens unnecessarily

Step 2: Implement token caching.
  - Ensure tokens are cached in Redis until 60s before expiry
  - Never refresh a token that has more than 60 seconds of validity remaining

Step 3: Review client implementations.
  - Check mobile app versions for premature token refresh bugs
  - Review backend service-to-service auth token handling

## Emergency Bypass
- If affecting > 1% of users: enable extended token lifetime (30d → 90d)
- Requires security team approval

## Monitoring
- Set alert at 80% of rate limit threshold
- Track token refresh frequency per user segment
        """,
        "last_updated": "2024-01-25",
    },
    {
        "id": "rb-008",
        "service": "inventory",
        "title": "Inventory Service: Stock Discrepancy Investigation",
        "content": """
# Inventory Stock Discrepancy Runbook

## Trigger Conditions
- Automated reconciliation detects discrepancy
- Warehouse reports incorrect stock levels
- Order fulfillment failures due to overselling

## Investigation Steps
Step 1: Quantify the discrepancy.
  - Run reconciliation report: SELECT sku, system_qty, warehouse_qty, 
    (system_qty - warehouse_qty) as delta FROM inventory_reconciliation
    WHERE ABS(system_qty - warehouse_qty) > 0;

Step 2: Identify time of divergence.
  - Check event log for last successful sync timestamp
  - Review failed sync jobs in Cloud Scheduler

Step 3: Root cause analysis.
  - Race condition in order processing + sync?
  - Manual warehouse adjustments not captured?
  - API request failures during high-traffic periods?

## Remediation
Step 4: Apply corrections.
  - If discrepancy < 10 items: auto-correct from warehouse source of truth
  - If discrepancy > 10 items: freeze affected SKUs, manual review required

Step 5: Prevent overselling.
  - Temporarily reduce available quantity by buffer (10%)
  - Enable "reserve on cart-add" rather than "reserve on checkout"

## Communication
- Notify warehouse operations team within 30 minutes of discovery
- If customer orders affected: trigger order review process
        """,
        "last_updated": "2024-02-05",
    },
    {
        "id": "rb-009",
        "service": "search",
        "title": "Search Service: Relevance Degradation Runbook",
        "content": """
# Search Relevance Degradation Runbook

## Trigger Conditions  
- User search abandonment rate increases > 20%
- Zero-result rate increases > 5 percentage points
- CTR on search results drops significantly

## Investigation
Step 1: Compare search quality metrics.
  - Before: pull metrics from 7 days ago
  - After: current metrics
  - Focus on NDCG (Normalized Discounted Cumulative Gain)

Step 2: Check recent changes.
  - Index mapping changes
  - Ranking algorithm updates  
  - Synonym dictionary updates
  - Stop word list changes

Step 3: Test with canary queries.
  - Run standard query set against both old and new results
  - "laptop" should return electronics, not accessories
  - "red shoes size 10" should be filtered correctly

## Rollback
Step 4: Revert recent changes.
  - Ranking algorithm: git revert + deploy
  - Index mappings: restore from snapshot
  - Synonyms: reload previous synonym file

## A/B Testing
- Always A/B test search ranking changes before full rollout
- Minimum test duration: 7 days with statistical significance p < 0.05
        """,
        "last_updated": "2024-03-10",
    },
    {
        "id": "rb-010",
        "service": "notifications",
        "title": "Notifications Service: Push Notification Delivery Failure",
        "content": """
# Push Notification Delivery Failure Runbook

## Trigger Conditions
- FCM/APNs delivery rate drops below 90%
- Push notification bounce rate increases
- Token registration failures spike

## Immediate Steps
Step 1: Check push provider status.
  - Firebase Cloud Messaging: https://status.firebase.google.com
  - Apple Push Notification Service: https://developer.apple.com/system-status

Step 2: Validate device token health.
  - Check percentage of invalid/expired tokens in database
  - If > 20% invalid tokens: trigger token refresh campaign

Step 3: Review notification payload.
  - FCM payload must be < 4KB (Android) or 4KB (iOS via FCM) or 5KB (APNs direct)
  - Check for special characters causing serialization issues
  - Validate required fields: title, body, sound

Step 4: Retry strategy.
  - Failed pushes should retry with exponential backoff (max 3 attempts)
  - After 3 failures: fall back to email notification if user opted in

## Token Management
- Implement token refresh on app launch
- Remove tokens that return "NotRegistered" or "InvalidRegistration" errors
- Batch token operations: max 500 tokens per FCM request

## Analytics
- Track delivery rate by platform (iOS/Android/Web) separately
- Monitor notification opt-out rates for anomalies
        """,
        "last_updated": "2024-03-25",
    },
]


def main() -> None:
    print(f"Seeding ChromaDB at: {CHROMADB_PERSIST_DIR}")

    # Initialize ChromaDB with persistent storage
    client = chromadb.PersistentClient(path=CHROMADB_PERSIST_DIR)

    # Use sentence-transformers embedding function
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    # Get or create collection
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # Upsert documents (idempotent)
    ids = [rb["id"] for rb in RUNBOOKS]
    documents = [rb["content"] for rb in RUNBOOKS]
    metadatas = [
        {
            "service": rb["service"],
            "title": rb["title"],
            "last_updated": rb["last_updated"],
        }
        for rb in RUNBOOKS
    ]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    count = collection.count()
    print(f"✓ Seeded {count} runbook documents into ChromaDB collection '{COLLECTION_NAME}'")

    # Quick sanity check
    results = collection.query(
        query_texts=["payment service high error rate"],
        n_results=2,
    )
    print("\nSanity check — top 2 results for 'payment service high error rate':")
    for i, (doc_id, metadata, distance) in enumerate(
        zip(
            results["ids"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ):
        print(f"  {i+1}. [{doc_id}] {metadata['title']} (distance={distance:.4f})")


if __name__ == "__main__":
    main()
