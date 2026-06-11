// Power-user "Dev" affordance: a modal with a YAML textarea that maps directly
// onto a FoldSubmitRequest and submits via the existing submitFold wrapper,
// bypassing the structured FoldControls form. Lets you submit arbitrary specs
// the form can't express — e.g. a homo-9-mer (copies: 9) or multi-ligand
// co-folds. project_id is injected from the store; job selection + the jobs
// query are wired exactly like FoldControls on success.
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { parse } from "yaml";

import { submitFold } from "../api/folding";
import { useJobsStore } from "../state/useJobsStore";
import type { FoldModel, FoldSubmitRequest, JobRef } from "../types";

const MODELS: FoldModel[] = ["boltz_2", "boltz_1", "chai_1r"];

const PLACEHOLDER_YAML = `# Boltz-2 direct submit — edit and Submit.
model: boltz_2
sequence_id: 1        # a saved sequence id (see the Sequence tab)
copies: 9             # fold 9 identical copies as one homo-oligomer complex
name: GvpA 9-mer
# --- or specify chains explicitly instead of sequence_id/copies ---
# protein_sequences: ["MAVEK...", "MAVEK..."]
# --- optional ligand co-fold ---
# ligand_smiles: ["CC(=O)Oc1ccccc1C(=O)O"]
# affinity_ligand_index: 0
`;

/**
 * Validate a parsed YAML object and project it onto a FoldSubmitRequest,
 * stripping unknown keys and injecting project_id. Returns either a ready body
 * or a human-readable error string. Pure — no side effects.
 */
function buildRequest(
  parsed: unknown,
  projectId: number,
): { body: FoldSubmitRequest } | { error: string } {
  if (parsed == null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { error: "YAML must define an object (key: value pairs)." };
  }
  const raw = parsed as Record<string, unknown>;

  // --- protein_sequences: optional array of non-empty strings ---
  let proteinSequences: string[] | undefined;
  if (raw.protein_sequences != null) {
    if (
      !Array.isArray(raw.protein_sequences) ||
      raw.protein_sequences.length === 0 ||
      !raw.protein_sequences.every((s) => typeof s === "string" && s.trim().length > 0)
    ) {
      return { error: "protein_sequences must be a non-empty array of sequence strings." };
    }
    proteinSequences = raw.protein_sequences as string[];
  }

  // --- sequence_id: optional number ---
  let sequenceId: number | undefined;
  if (raw.sequence_id != null) {
    if (typeof raw.sequence_id !== "number" || !Number.isFinite(raw.sequence_id)) {
      return { error: "sequence_id must be a number." };
    }
    sequenceId = raw.sequence_id;
  }

  // Must give a sequence_id OR a non-empty protein_sequences.
  if (sequenceId == null && proteinSequences == null) {
    return {
      error: "Provide a numeric sequence_id OR a non-empty protein_sequences array.",
    };
  }

  // --- copies: optional integer >= 1 ---
  let copies: number | undefined;
  if (raw.copies != null) {
    if (typeof raw.copies !== "number" || !Number.isInteger(raw.copies) || raw.copies < 1) {
      return { error: "copies must be an integer >= 1." };
    }
    copies = raw.copies;
  }

  // --- model: optional, must be a known model; default boltz_2 ---
  let model: FoldModel = "boltz_2";
  if (raw.model != null) {
    if (typeof raw.model !== "string" || !MODELS.includes(raw.model as FoldModel)) {
      return { error: `model must be one of: ${MODELS.join(", ")}.` };
    }
    model = raw.model as FoldModel;
  }

  // --- partner_sequence_id: optional number ---
  let partnerSequenceId: number | undefined;
  if (raw.partner_sequence_id != null) {
    if (
      typeof raw.partner_sequence_id !== "number" ||
      !Number.isFinite(raw.partner_sequence_id)
    ) {
      return { error: "partner_sequence_id must be a number." };
    }
    partnerSequenceId = raw.partner_sequence_id;
  }

  // --- ligand_smiles: optional array of strings ---
  let ligandSmiles: string[] | undefined;
  if (raw.ligand_smiles != null) {
    if (
      !Array.isArray(raw.ligand_smiles) ||
      !raw.ligand_smiles.every((s) => typeof s === "string")
    ) {
      return { error: "ligand_smiles must be an array of SMILES strings." };
    }
    ligandSmiles = raw.ligand_smiles as string[];
  }

  // --- affinity_ligand_index: optional number ---
  let affinityLigandIndex: number | undefined;
  if (raw.affinity_ligand_index != null) {
    if (
      typeof raw.affinity_ligand_index !== "number" ||
      !Number.isInteger(raw.affinity_ligand_index) ||
      raw.affinity_ligand_index < 0
    ) {
      return { error: "affinity_ligand_index must be a non-negative integer." };
    }
    affinityLigandIndex = raw.affinity_ligand_index;
  }

  // --- name: optional string ---
  let name: string | undefined;
  if (raw.name != null) {
    if (typeof raw.name !== "string") {
      return { error: "name must be a string." };
    }
    name = raw.name;
  }

  // Only forward known fields + the injected project_id.
  const body: FoldSubmitRequest = { project_id: projectId, model };
  if (sequenceId != null) body.sequence_id = sequenceId;
  if (proteinSequences != null) body.protein_sequences = proteinSequences;
  if (copies != null) body.copies = copies;
  if (partnerSequenceId != null) body.partner_sequence_id = partnerSequenceId;
  if (ligandSmiles != null) body.ligand_smiles = ligandSmiles;
  if (affinityLigandIndex != null) body.affinity_ligand_index = affinityLigandIndex;
  if (name != null) body.name = name;

  return { body };
}

export function DevSubmitPanel({ onClose }: { onClose: () => void }) {
  const projectId = useJobsStore((s) => s.projectId);
  const setSelectedJobId = useJobsStore((s) => s.setSelectedJobId);
  const setActiveBatchRunId = useJobsStore((s) => s.setActiveBatchRunId);
  const qc = useQueryClient();

  const [text, setText] = useState(PLACEHOLDER_YAML);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [result, setResult] = useState<JobRef | null>(null);

  // Esc closes the modal.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const foldMutation = useMutation({
    mutationFn: (body: FoldSubmitRequest) => submitFold(body),
    onSuccess: (ref) => {
      setResult(ref);
      setSelectedJobId(ref.job_id);
      setActiveBatchRunId(null);
      qc.invalidateQueries({ queryKey: ["jobs", projectId] });
      // Briefly show the new job id/state, then close.
      window.setTimeout(onClose, 1200);
    },
  });

  const submitError = foldMutation.isError
    ? String((foldMutation.error as Error).message)
    : null;

  function handleSubmit() {
    setValidationError(null);
    setResult(null);
    foldMutation.reset();

    let parsed: unknown;
    try {
      parsed = parse(text);
    } catch (e) {
      setValidationError(`YAML parse error: ${String((e as Error).message)}`);
      return;
    }

    const built = buildRequest(parsed, projectId);
    if ("error" in built) {
      setValidationError(built.error);
      return;
    }
    foldMutation.mutate(built.body);
  }

  // Backdrop click (but not clicks inside the card) closes.
  const busy = foldMutation.isPending;
  const shownError = validationError ?? submitError;
  const summary = useMemo(() => result && JSON.stringify(result, null, 2), [result]);

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label="Direct submit (YAML)"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="modal-card__head">
          <div className="modal-card__titlewrap">
            <span className="modal-card__title">Direct submit (YAML)</span>
            <span className="modal-card__sub">Bypass the form — paste a Boltz-2 fold spec</span>
          </div>
          <button className="btn btn--ghost btn--icon" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <p className="modal-card__hint small muted">
          Maps directly onto the fold-submit request. Give a numeric{" "}
          <code>sequence_id</code> or an explicit <code>protein_sequences</code> list. Use{" "}
          <code>copies: N</code> for a homo-oligomer. <code>project_id</code> is injected
          automatically.
        </p>

        <div className="field">
          <label className="label" htmlFor="dev-yaml">
            YAML spec
          </label>
          <textarea
            id="dev-yaml"
            className="input input--mono textarea"
            rows={12}
            spellCheck={false}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={busy}
          />
        </div>

        {shownError && <p className="text-error small">{shownError}</p>}

        {result && (
          <div className="modal-card__result">
            <span className="chip chip--action">
              Submitted · job #{result.job_id} · {result.state}
            </span>
            {summary && <pre className="modal-card__resultjson">{summary}</pre>}
          </div>
        )}

        <div className="modal-card__actions row row--between">
          <span className="small muted">Esc or click outside to close</span>
          <div className="row">
            <button className="btn btn--ghost" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button className="btn btn--primary" onClick={handleSubmit} disabled={busy}>
              {busy ? "Submitting…" : "Submit"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
