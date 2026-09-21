// Mirrors src/api/schemas.py -- keep in sync by hand (no shared codegen yet).

export interface DashboardSummary {
  total_customers: number;
  scored_customers: number;
  high_risk_count: number;
  mean_churn_probability: number;
  revenue_at_risk: number;
  mean_predicted_clv: number;
  segment_distribution: Record<string, number>;
  prediction_date: string;
}

export interface CustomerListItem {
  customer_id: string;
  plan: string;
  country: string;
  acquisition_channel: string;
  churn_probability: number | null;
  predicted_clv: number | null;
  segment: string | null;
}

export interface CustomerListResponse {
  total: number;
  page: number;
  page_size: number;
  items: CustomerListItem[];
}

export interface RfmSummary {
  recency_days: number | null;
  frequency: number;
  monetary: number;
}

export interface CustomerDetail {
  customer_id: string;
  signup_date: string;
  country: string;
  acquisition_channel: string;
  plan: string;
  churn_probability: number | null;
  predicted_clv: number | null;
  segment: string | null;
  rfm: RfmSummary;
}

export interface HistoryEvent {
  event_time: string;
  event_source: "order" | "interaction" | "support";
  description: string;
  amount: number | null;
}

export interface CustomerHistoryResponse {
  customer_id: string;
  total_events: number;
  events: HistoryEvent[];
}

export interface SegmentSummary {
  segment: string;
  size: number;
  mean_churn_probability: number;
  mean_predicted_clv: number;
}

export interface SegmentDetail {
  summary: SegmentSummary;
  top_at_risk: CustomerListItem[];
}

export interface ChurnByDimension {
  dimension: string;
  value: string;
  n: number;
  mean_churn_probability: number;
}

export interface CohortRow {
  cohort_month: string;
  cohort_age_months: number;
  retained_pct: number;
}

export interface ModelMetrics {
  model_name: string;
  model_version: string;
  trained_at: string;
  metrics: Record<string, number>;
}

export interface DriverContribution {
  feature: string;
  shap_value: number;
  feature_value: number;
}

export interface ExplanationResponse {
  customer_id: string;
  model_version: string;
  prediction_date: string;
  top_drivers: DriverContribution[];
}

export interface HealthCheck {
  status: string;
  database_connected: boolean;
  table_row_counts: Record<string, number>;
  latest_order_date: string | null;
  latest_prediction_date: string | null;
}

export interface DriftMetric {
  metric_name: string;
  kind: "feature" | "prediction";
  psi: number;
  severity: "stable" | "moderate" | "significant";
  reference_mean: number;
  current_mean: number;
}

export interface DriftReportResponse {
  model_name: string;
  report_date: string;
  feature_drift: DriftMetric[];
  prediction_drift: DriftMetric[];
  has_prediction_baseline: boolean;
}
