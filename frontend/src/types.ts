// Frontend types mirroring backend/app/schemas.py. FROZEN CONTRACT — Phase-1
// agents (D, E) import these; do not redefine equivalent shapes. Wire JSON is
// snake_case to match the backend.

export interface Project {
  id: number;
  name: string;
  created_at: string;
}

export interface Sequence {
  id: number;
  project_id: number;
  name: string;
  residues: string;
  length: number;
  kind: string; // protein | antigen | partner
  parent_id: number | null;
  created_at: string;
}

export interface SequenceCreate {
  project_id: number;
  name: string;
  residues: string;
  kind?: "protein" | "antigen" | "partner";
  parent_id?: number | null;
}

export interface SequenceUpdate {
  name?: string;
  residues?: string;
  kind?: "protein" | "antigen" | "partner";
}

export type FoldModel = "boltz_2" | "boltz_1" | "chai_1r";

export interface FoldSubmitRequest {
  project_id: number;
  protein_sequences?: string[];
  sequence_id?: number | null;
  partner_sequence_id?: number | null;
  /** Fold this many identical copies of the single sequence as a homo-oligomer (e.g. 9 for a 9-mer). */
  copies?: number;
  ligand_smiles?: string[];
  affinity_ligand_index?: number | null;
  model?: FoldModel;
  name?: string;
}

export interface BatchFoldItem {
  label: string;
  protein_sequences: string[];
  ligand_smiles?: string[];
  affinity_ligand_index?: number | null;
}

export interface BatchFoldRequest {
  project_id: number;
  batch_run_id?: number | null;
  name?: string;
  items: BatchFoldItem[];
  model?: FoldModel;
  partner_sequence_id?: number | null;
}

export interface JobRef {
  job_id: number;
  provider_job_id: string;
  state: string;
  label: string;
}

export interface BatchSubmitResponse {
  batch_run_id: number;
  jobs: JobRef[];
}

export interface PerModel {
  ptm?: number | null;
  iptm?: number | null;
  avg_lddt?: number | null;
  confidence?: number | null;
  affinity_pred_value?: number | null;
  affinity_probability?: number | null;
  strain?: number | null;
  posebusters_valid?: boolean | null;
}

export type JobState = "queued" | "running" | "completed" | "failed" | "stopped";

export interface FoldJob {
  id: number;
  project_id: number;
  batch_run_id: number | null;
  sequence_id: number | null;
  label: string;
  provider: string;
  provider_job_id: string;
  model: string;
  state: JobState | string;
  raw_status: string | null;
  scores: Record<string, number | null> | null;
  per_model: PerModel[] | null;
  structure_format: string | null;
  has_structure: boolean;
  error: string | null;
  rank_hint: number | null;
  submitted_at: string;
  updated_at: string;
}

export interface BatchRun {
  id: number;
  project_id: number;
  name: string;
  base_sequence_id: number | null;
  partner_sequence_id: number | null;
  strategy: string;
  status: string;
  counts: Record<string, number>;
  created_at: string;
}

export type VariantStrategy = "positions_subs" | "alanine_scan" | "claude" | "pasted";

export interface VariantGenerateRequest {
  base_sequence_id: number;
  strategy: VariantStrategy;
  params?: Record<string, unknown>;
}

export interface Variant {
  label: string;
  residues: string;
  mutations: string[];
}

export interface VariantGenerateResponse {
  base_sequence_id: number;
  variants: Variant[];
}

// ---- Viewer directives (mirror schemas.Directive) ----
export interface DirectiveTarget {
  chain?: string;
  residue?: number;
  residues?: number[];
  residue_range?: [number, number]; // inclusive, 1-indexed
}

export type DirectiveKind = "color" | "label" | "representation" | "focus" | "select";

export interface Directive {
  kind: DirectiveKind;
  target: DirectiveTarget;
  color?: string; // hex, kind="color"
  text?: string; // kind="label"
  repr?: string; // kind="representation"
}

// ---- Chat ----
export interface ChatRequest {
  project_id: number;
  message: string;
  context?: Record<string, unknown>;
}

export type SSEEventName = "text" | "directive" | "tool_result" | "job" | "done" | "error";

// ---- Viewer picking ----
export interface PickSelection {
  chain?: string;
  residue?: number;
  resName?: string;
}
