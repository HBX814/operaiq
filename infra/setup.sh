#!/usr/bin/env bash
# OperaIQ Infrastructure Setup Script
# Creates BigQuery dataset, tables, Pub/Sub topic, and Firestore DB
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-operaiq}"
DATASET_ID="${BQ_DATASET:-operaiq}"
REGION="${GCP_REGION:-us-central1}"

echo "🚀 Setting up OperaIQ infrastructure in project: $PROJECT_ID"

# ─── BigQuery ─────────────────────────────────────────────────────────────────
echo ""
echo "📦 Creating BigQuery dataset: $DATASET_ID"
bq --project_id="$PROJECT_ID" mk \
  --dataset \
  --location=US \
  --description="OperaIQ production events and audit logs" \
  "$DATASET_ID" || echo "Dataset already exists"

echo "📊 Creating events table..."
bq --project_id="$PROJECT_ID" mk \
  --table \
  --time_partitioning_field=timestamp \
  --time_partitioning_type=DAY \
  --clustering_fields=service,event_type \
  --description="All production events: deployments, metrics, incidents" \
  "${DATASET_ID}.events" \
  ../data/schema/events.json || echo "Table may already exist"

echo "📝 Creating audit_log table..."
bq --project_id="$PROJECT_ID" mk \
  --table \
  --time_partitioning_field=timestamp \
  --time_partitioning_type=DAY \
  --description="MCP tool call audit log" \
  "${DATASET_ID}.audit_log" \
  ../data/schema/audit.json || echo "Table may already exist"

# ─── Pub/Sub ──────────────────────────────────────────────────────────────────
echo ""
echo "📨 Creating Pub/Sub topic: operaiq-events"
gcloud pubsub topics create operaiq-events \
  --project="$PROJECT_ID" 2>/dev/null || echo "Topic already exists"

echo "📥 Creating BigQuery subscription for operaiq-events..."
gcloud pubsub subscriptions create operaiq-events-bq \
  --topic=operaiq-events \
  --bigquery-table="${PROJECT_ID}:${DATASET_ID}.events" \
  --use-topic-schema=false \
  --write-metadata=false \
  --project="$PROJECT_ID" 2>/dev/null || echo "Subscription may already exist"

# ─── Firestore ────────────────────────────────────────────────────────────────
echo ""
echo "🔥 Ensuring Firestore database exists..."
gcloud firestore databases create \
  --location="$REGION" \
  --project="$PROJECT_ID" 2>/dev/null || echo "Firestore DB already exists"

# ─── Cloud Run Service Accounts ───────────────────────────────────────────────
echo ""
echo "🔐 Creating service accounts..."

# MCP Server SA
gcloud iam service-accounts create operaiq-mcp-server \
  --display-name="OperaIQ MCP Server" \
  --project="$PROJECT_ID" 2>/dev/null || echo "SA already exists"

# Agent SA
gcloud iam service-accounts create operaiq-agents \
  --display-name="OperaIQ Agent Service" \
  --project="$PROJECT_ID" 2>/dev/null || echo "SA already exists"

# Grant permissions
echo "🔑 Granting IAM permissions..."
for ROLE in "roles/bigquery.dataEditor" "roles/bigquery.jobUser" "roles/pubsub.publisher" "roles/datastore.user"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:operaiq-mcp-server@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$ROLE" --quiet
done

for ROLE in "roles/aiplatform.user"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:operaiq-agents@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$ROLE" --quiet
done

echo ""
echo "✅ Infrastructure setup complete!"
echo ""
echo "Next steps:"
echo "  1. Seed ChromaDB: python data/seed_runbooks.py"
echo "  2. Start MCP Server: cd mcp-server && python main.py"
echo "  3. Start Agents: cd agents && python main.py"
echo "  4. Start Frontend: cd frontend && npm run dev"
