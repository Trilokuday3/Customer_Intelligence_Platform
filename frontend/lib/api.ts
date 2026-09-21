import type {
  ChurnByDimension,
  CohortRow,
  CustomerDetail,
  CustomerHistoryResponse,
  CustomerListResponse,
  DashboardSummary,
  DriftReportResponse,
  ExplanationResponse,
  HealthCheck,
  ModelMetrics,
  SegmentDetail,
  SegmentSummary,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, cache: "no-store" });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch("/dashboard/summary");
}

export interface CustomerListParams {
  search?: string;
  segment?: string;
  plan?: string;
  min_churn_probability?: number;
  max_churn_probability?: number;
  min_predicted_clv?: number;
  sort_by?: "churn_probability" | "predicted_clv";
  page?: number;
  page_size?: number;
}

export function listCustomers(params: CustomerListParams = {}): Promise<CustomerListResponse> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const qs = query.toString();
  return apiFetch(`/customers${qs ? `?${qs}` : ""}`);
}

export function getCustomer(customerId: string): Promise<CustomerDetail> {
  return apiFetch(`/customers/${encodeURIComponent(customerId)}`);
}

export function getCustomerHistory(customerId: string): Promise<CustomerHistoryResponse> {
  return apiFetch(`/customers/${encodeURIComponent(customerId)}/history`);
}

export function listSegments(): Promise<SegmentSummary[]> {
  return apiFetch("/segments");
}

export function getSegment(name: string): Promise<SegmentDetail> {
  return apiFetch(`/segments/${encodeURIComponent(name)}`);
}

export function getChurnByDimension(dimension: "plan" | "acquisition_channel" | "country"): Promise<ChurnByDimension[]> {
  return apiFetch(`/analytics/churn?dimension=${dimension}`);
}

export function getCohorts(): Promise<CohortRow[]> {
  return apiFetch("/analytics/cohorts");
}

export function getModelMetrics(modelName: "churn" | "clv"): Promise<ModelMetrics> {
  return apiFetch(`/models/${modelName}`);
}

export function getExplanation(customerId: string): Promise<ExplanationResponse> {
  return apiFetch(`/explanations/${encodeURIComponent(customerId)}`);
}

export function getHealth(): Promise<HealthCheck> {
  return apiFetch("/monitoring/health");
}

export function getDrift(modelName: "churn" | "clv"): Promise<DriftReportResponse> {
  return apiFetch(`/monitoring/drift/${modelName}`);
}
