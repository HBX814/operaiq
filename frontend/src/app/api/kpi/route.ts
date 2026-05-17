import { NextRequest, NextResponse } from "next/server";
import { BigQuery } from "@google-cloud/bigquery";

const PROJECT_ID = process.env.GCP_PROJECT_ID || "operaiq";
const DATASET_ID = process.env.BIGQUERY_DATASET || "operaiq";
const EVENTS_TABLE = `${PROJECT_ID}.${DATASET_ID}.events`;

const bq = new BigQuery({ projectId: PROJECT_ID });

export async function GET(request: NextRequest) {
  try {
    const query = `
      SELECT
        (SELECT COUNT(*) FROM \`${EVENTS_TABLE}\` WHERE event_type = 'incident' AND status = 'open' AND severity = 'critical') as activeIncidents,
        (SELECT COUNT(*) FROM \`${EVENTS_TABLE}\` WHERE event_type = 'deployment' AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)) as deploymentsToday,
        (SELECT AVG(CAST(value as FLOAT64)) FROM \`${EVENTS_TABLE}\` WHERE event_type = 'metric' AND metric_type = 'error_rate' AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)) as errorRate,
        (SELECT AVG(CAST(value as FLOAT64)) FROM \`${EVENTS_TABLE}\` WHERE event_type = 'metric' AND metric_type = 'latency_p99' AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)) as p99Latency
    `;

    const [rows] = await bq.query({ query });
    const stats = rows[0];

    return NextResponse.json({
      activeIncidents: Number(stats.activeIncidents || 0),
      deploymentsToday: Number(stats.deploymentsToday || 0),
      errorRate: Number(stats.errorRate || 0).toFixed(2) + "%",
      p99Latency: Number(stats.p99Latency || 0).toFixed(0) + "ms"
    });
  } catch (error) {
    console.error("Error fetching KPI stats:", error);
    return NextResponse.json({
      activeIncidents: 0,
      deploymentsToday: 0,
      errorRate: "0.00%",
      p99Latency: "0ms",
      error: error instanceof Error ? error.message : String(error)
    }, { status: 500 });
  }
}
