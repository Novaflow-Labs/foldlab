// Typed wrappers over api/client.ts for folding: jobs, batches, projects.
import { apiGet, apiPost } from "./client";
import type {
  BatchFoldRequest,
  BatchRun,
  BatchSubmitResponse,
  FoldJob,
  FoldSubmitRequest,
  JobRef,
  Project,
} from "../types";

export function listProjects(): Promise<Project[]> {
  return apiGet<Project[]>(`/projects`);
}

export function submitFold(body: FoldSubmitRequest): Promise<JobRef> {
  return apiPost<JobRef>(`/fold`, body);
}

export function submitBatch(body: BatchFoldRequest): Promise<BatchSubmitResponse> {
  return apiPost<BatchSubmitResponse>(`/fold/batch`, body);
}

export function listJobs(projectId: number, batchRunId?: number): Promise<FoldJob[]> {
  return apiGet<FoldJob[]>(
    `/jobs?project_id=${projectId}${batchRunId != null ? `&batch_run_id=${batchRunId}` : ""}`,
  );
}

export function getJob(id: number): Promise<FoldJob> {
  return apiGet<FoldJob>(`/jobs/${id}`);
}

export function listBatches(projectId: number): Promise<BatchRun[]> {
  return apiGet<BatchRun[]>(`/batches?project_id=${projectId}`);
}
