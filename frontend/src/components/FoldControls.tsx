// Submit a single fold: pick the sequence, optional partner/antigen, optional
// ligand SMILES + affinity, and a model. Selects the new job on success.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listJobs, submitFold } from "../api/folding";
import { useJobsStore } from "../state/useJobsStore";
import type { FoldJob, FoldModel } from "../types";
import { JobBadge } from "./JobBadge";
import { useSequences } from "./SequenceEditor";

const MODELS: { value: FoldModel; label: string }[] = [
  { value: "boltz_2", label: "Boltz-2" },
  { value: "boltz_1", label: "Boltz-1" },
  { value: "chai_1r", label: "Chai-1r" },
];

/**
 * Shared jobs query with adaptive polling: refetch every 3s while any job is
 * queued/running, otherwise stop. Consumed by FoldControls + ResultsGallery.
 */
export function useJobs(projectId: number) {
  return useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => listJobs(projectId),
    refetchInterval: (q) =>
      q.state.data?.some((j) => j.state === "queued" || j.state === "running") ? 3000 : false,
  });
}

export function FoldControls() {
  const projectId = useJobsStore((s) => s.projectId);
  const setSelectedJobId = useJobsStore((s) => s.setSelectedJobId);
  const setActiveBatchRunId = useJobsStore((s) => s.setActiveBatchRunId);
  const qc = useQueryClient();

  const { data: sequences = [] } = useSequences(projectId);
  const { data: jobs = [] } = useJobs(projectId);

  const [sequenceId, setSequenceId] = useState<number | null>(null);
  const [partnerId, setPartnerId] = useState<number | null>(null);
  const [ligand, setLigand] = useState("");
  const [affinity, setAffinity] = useState(false);
  const [model, setModel] = useState<FoldModel>("boltz_2");
  const [lastJobId, setLastJobId] = useState<number | null>(null);

  const ligandList = ligand
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter(Boolean);

  const foldMutation = useMutation({
    mutationFn: () =>
      submitFold({
        project_id: projectId,
        sequence_id: sequenceId,
        partner_sequence_id: partnerId,
        ligand_smiles: ligandList.length ? ligandList : undefined,
        affinity_ligand_index: affinity && ligandList.length ? 0 : null,
        model,
      }),
    onSuccess: (ref) => {
      setLastJobId(ref.job_id);
      setSelectedJobId(ref.job_id);
      setActiveBatchRunId(null);
      qc.invalidateQueries({ queryKey: ["jobs", projectId] });
    },
  });

  const lastJob: FoldJob | undefined = jobs.find((j) => j.id === lastJobId);
  const canFold = sequenceId != null && !foldMutation.isPending;

  return (
    <div className="stack">
      <div className="field">
        <label className="label">Protein to fold</label>
        <select
          className="input"
          value={sequenceId ?? ""}
          onChange={(e) => setSequenceId(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Select a sequence…</option>
          {sequences.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.length} aa)
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label className="label">Partner / antigen (optional)</label>
        <select
          className="input"
          value={partnerId ?? ""}
          onChange={(e) => setPartnerId(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">None (monomer)</option>
          {sequences
            .filter((s) => s.id !== sequenceId)
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.kind})
              </option>
            ))}
        </select>
      </div>

      <div className="field">
        <label className="label">Ligand SMILES (optional)</label>
        <input
          className="input input--mono"
          value={ligand}
          placeholder="e.g. CC(=O)Oc1ccccc1C(=O)O"
          onChange={(e) => setLigand(e.target.value)}
        />
        {ligandList.length > 0 && (
          <label className="checkbox small">
            <input
              type="checkbox"
              checked={affinity}
              onChange={(e) => setAffinity(e.target.checked)}
            />
            Predict binding affinity for first ligand
          </label>
        )}
      </div>

      <div className="field">
        <label className="label">Model</label>
        <div className="segmented">
          {MODELS.map((m) => (
            <button
              key={m.value}
              className={`segmented__opt ${model === m.value ? "is-active" : ""}`}
              onClick={() => setModel(m.value)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <button className="btn btn--primary btn--block" disabled={!canFold} onClick={() => foldMutation.mutate()}>
        {foldMutation.isPending ? "Submitting…" : "Fold"}
      </button>

      {foldMutation.isError && (
        <p className="text-error small">{String((foldMutation.error as Error).message)}</p>
      )}

      {lastJob && (
        <div className="job-inline" onClick={() => setSelectedJobId(lastJob.id)}>
          <span className="job-inline__label">{lastJob.label}</span>
          <JobBadge state={lastJob.state} />
        </div>
      )}
    </div>
  );
}
