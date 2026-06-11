// Typed wrappers over api/client.ts for the /sequences resource.
import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type { Sequence, SequenceCreate, SequenceUpdate } from "../types";

export function listSequences(projectId: number): Promise<Sequence[]> {
  return apiGet<Sequence[]>(`/sequences?project_id=${projectId}`);
}

export function getSequence(id: number): Promise<Sequence> {
  return apiGet<Sequence>(`/sequences/${id}`);
}

export function createSequence(body: SequenceCreate): Promise<Sequence> {
  return apiPost<Sequence>(`/sequences`, body);
}

export function updateSequence(id: number, body: SequenceUpdate): Promise<Sequence> {
  return apiPut<Sequence>(`/sequences/${id}`, body);
}

export function deleteSequence(id: number): Promise<void> {
  return apiDelete(`/sequences/${id}`);
}
