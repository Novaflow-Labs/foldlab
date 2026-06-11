// Generate sequence variants (positions_subs / alanine_scan / pasted / claude),
// preview them, then batch-fold and jump to the filtered ResultsGallery.
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { submitBatch } from "../api/folding";
import { generateVariants } from "../api/variants";
import { useJobsStore } from "../state/useJobsStore";
import type { FoldModel, Variant, VariantStrategy } from "../types";
import { useSequences } from "./SequenceEditor";

const STRATEGIES: { value: VariantStrategy; label: string }[] = [
  { value: "positions_subs", label: "Position substitutions" },
  { value: "alanine_scan", label: "Alanine scan" },
  { value: "pasted", label: "Pasted sequences" },
  { value: "claude", label: "Claude (AI-designed)" },
];

const MODELS: FoldModel[] = ["boltz_2", "boltz_1", "chai_1r"];

export function VariantPanel() {
  const projectId = useJobsStore((s) => s.projectId);
  const setActiveBatchRunId = useJobsStore((s) => s.setActiveBatchRunId);
  const qc = useQueryClient();

  const { data: sequences = [] } = useSequences(projectId);

  const [baseId, setBaseId] = useState<number | null>(null);
  const [strategy, setStrategy] = useState<VariantStrategy>("positions_subs");
  const [model, setModel] = useState<FoldModel>("boltz_2");
  const [partnerId, setPartnerId] = useState<number | null>(null);

  // Strategy-specific params.
  const [positions, setPositions] = useState(""); // e.g. "5,12,30"
  const [aminoAcids, setAminoAcids] = useState("A,G,L,V"); // candidate residues
  const [pasted, setPasted] = useState(""); // one sequence per line
  const [prompt, setPrompt] = useState(""); // claude instruction
  const [count, setCount] = useState(5); // claude / count cap

  const [variants, setVariants] = useState<Variant[]>([]);

  const params = useMemo<Record<string, unknown>>(() => {
    switch (strategy) {
      case "positions_subs":
        return {
          positions: positions
            .split(/[\s,]+/)
            .map((n) => Number(n))
            .filter((n) => Number.isInteger(n) && n > 0),
          substitutions: aminoAcids
            .split(/[\s,]+/)
            .map((s) => s.trim().toUpperCase())
            .filter(Boolean),
        };
      case "alanine_scan":
        return {
          positions: positions
            .split(/[\s,]+/)
            .map((n) => Number(n))
            .filter((n) => Number.isInteger(n) && n > 0),
        };
      case "pasted":
        return {
          sequences: pasted
            .split(/\r?\n/)
            .map((s) => s.trim())
            .filter(Boolean),
        };
      case "claude":
        return { n: count, rationale_prompt: prompt };
    }
  }, [strategy, positions, aminoAcids, pasted, prompt, count]);

  const genMutation = useMutation({
    mutationFn: () => {
      if (baseId == null) throw new Error("Pick a base sequence first.");
      return generateVariants({ base_sequence_id: baseId, strategy, params });
    },
    onSuccess: (res) => setVariants(res.variants),
  });

  const batchMutation = useMutation({
    mutationFn: () => {
      const partner = sequences.find((s) => s.id === partnerId);
      return submitBatch({
        project_id: projectId,
        name: `Variants of seq #${baseId}`,
        model,
        partner_sequence_id: partnerId,
        items: variants.map((v) => ({
          label: v.label,
          protein_sequences: partner ? [v.residues, partner.residues] : [v.residues],
        })),
      });
    },
    onSuccess: (res) => {
      setActiveBatchRunId(res.batch_run_id);
      qc.invalidateQueries({ queryKey: ["jobs", projectId] });
      qc.invalidateQueries({ queryKey: ["batches", projectId] });
    },
  });

  const needsPositions = strategy === "positions_subs" || strategy === "alanine_scan";

  return (
    <div className="stack">
      <div className="field">
        <label className="label">Base sequence</label>
        <select
          className="input"
          value={baseId ?? ""}
          onChange={(e) => setBaseId(e.target.value ? Number(e.target.value) : null)}
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
        <label className="label">Strategy</label>
        <select
          className="input"
          value={strategy}
          onChange={(e) => setStrategy(e.target.value as VariantStrategy)}
        >
          {STRATEGIES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {needsPositions && (
        <div className="field">
          <label className="label">Positions (1-indexed)</label>
          <input
            className="input input--mono"
            value={positions}
            placeholder="e.g. 5, 12, 30 (blank = scan all)"
            onChange={(e) => setPositions(e.target.value)}
          />
        </div>
      )}

      {strategy === "positions_subs" && (
        <div className="field">
          <label className="label">Candidate residues</label>
          <input
            className="input input--mono"
            value={aminoAcids}
            placeholder="A, G, L, V"
            onChange={(e) => setAminoAcids(e.target.value)}
          />
        </div>
      )}

      {strategy === "pasted" && (
        <div className="field">
          <label className="label">Sequences (one per line)</label>
          <textarea
            className="input input--mono textarea"
            value={pasted}
            rows={4}
            spellCheck={false}
            onChange={(e) => setPasted(e.target.value)}
          />
        </div>
      )}

      {strategy === "claude" && (
        <>
          <div className="field">
            <label className="label">Design instruction</label>
            <textarea
              className="input textarea"
              value={prompt}
              rows={3}
              placeholder="e.g. Improve thermostability while preserving the active site."
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="label">How many variants</label>
            <input
              className="input input--sm"
              type="number"
              min={1}
              max={20}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
            />
          </div>
        </>
      )}

      <button
        className="btn btn--primary btn--block"
        disabled={baseId == null || genMutation.isPending}
        onClick={() => genMutation.mutate()}
      >
        {genMutation.isPending ? "Generating…" : "Generate variants"}
      </button>

      {genMutation.isError && (
        <p className="text-error small">{String((genMutation.error as Error).message)}</p>
      )}

      {variants.length > 0 && (
        <div className="stack stack--tight">
          <div className="row row--between">
            <span className="label label--inline">{variants.length} variants</span>
            <button className="btn btn--link" onClick={() => setVariants([])}>
              Clear
            </button>
          </div>
          <ul className="variant-list">
            {variants.map((v, i) => (
              <li className="variant" key={i}>
                <span className="variant__label">{v.label}</span>
                <span className="variant__muts">
                  {v.mutations.length ? v.mutations.join(", ") : "—"}
                </span>
              </li>
            ))}
          </ul>

          <div className="field">
            <label className="label">Co-fold with partner (optional)</label>
            <select
              className="input"
              value={partnerId ?? ""}
              onChange={(e) => setPartnerId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">None</option>
              {sequences
                .filter((s) => s.id !== baseId)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.kind})
                  </option>
                ))}
            </select>
          </div>

          <div className="field">
            <label className="label">Model</label>
            <select
              className="input"
              value={model}
              onChange={(e) => setModel(e.target.value as FoldModel)}
            >
              {MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <button
            className="btn btn--accent btn--block"
            disabled={batchMutation.isPending}
            onClick={() => batchMutation.mutate()}
          >
            {batchMutation.isPending ? "Submitting batch…" : `Batch fold ${variants.length} variants`}
          </button>
          {batchMutation.isError && (
            <p className="text-error small">{String((batchMutation.error as Error).message)}</p>
          )}
          {batchMutation.isSuccess && (
            <p className="text-ok small">Batch submitted — see Results.</p>
          )}
        </div>
      )}
    </div>
  );
}
