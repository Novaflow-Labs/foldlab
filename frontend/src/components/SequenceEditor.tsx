// Sequence list + controlled editor with live validation, create/update, paste,
// and a "load demo" affordance.
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createSequence,
  deleteSequence,
  listSequences,
  updateSequence,
} from "../api/sequences";
import { DEMO_SEQUENCE, rulerRows, validateSequence } from "../lib/sequence";
import { useJobsStore } from "../state/useJobsStore";
import type { Sequence } from "../types";
import { PlusIcon } from "../ui/icons";

const KINDS = ["protein", "antigen", "partner"] as const;
type Kind = (typeof KINDS)[number];

/** Shared sequences query — also consumed by FoldControls / VariantPanel. */
export function useSequences(projectId: number) {
  return useQuery({
    queryKey: ["sequences", projectId],
    queryFn: () => listSequences(projectId),
  });
}

export function SequenceEditor() {
  const projectId = useJobsStore((s) => s.projectId);
  const qc = useQueryClient();
  const { data: sequences = [], isLoading } = useSequences(projectId);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Kind>("protein");
  const [draft, setDraft] = useState("");

  const selected = useMemo(
    () => sequences.find((s) => s.id === selectedId) ?? null,
    [sequences, selectedId],
  );

  // Load the selected sequence into the editable form.
  useEffect(() => {
    if (selected) {
      setName(selected.name);
      setKind((selected.kind as Kind) ?? "protein");
      setDraft(selected.residues);
    }
  }, [selected]);

  const validation = useMemo(() => validateSequence(draft), [draft]);
  const isDirty =
    !selected ||
    selected.name !== name ||
    selected.kind !== kind ||
    selected.residues !== validation.cleaned;

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (selectedId == null) {
        return createSequence({
          project_id: projectId,
          name: name.trim() || "Untitled",
          residues: validation.cleaned,
          kind,
        });
      }
      return updateSequence(selectedId, {
        name: name.trim() || "Untitled",
        residues: validation.cleaned,
        kind,
      });
    },
    onSuccess: (saved: Sequence) => {
      qc.invalidateQueries({ queryKey: ["sequences", projectId] });
      setSelectedId(saved.id);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteSequence(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sequences", projectId] });
      newSequence();
    },
  });

  function newSequence() {
    setSelectedId(null);
    setName("");
    setKind("protein");
    setDraft("");
  }

  const rows = rulerRows(validation.cleaned);

  return (
    <div className="stack">
      <div className="row row--between">
        <div className="field field--grow">
          <label className="label">Sequence</label>
          <select
            className="input"
            value={selectedId ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "") newSequence();
              else setSelectedId(Number(v));
            }}
          >
            <option value="">+ New sequence</option>
            {sequences.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.length} aa · {s.kind})
              </option>
            ))}
          </select>
        </div>
        <button
          className="btn btn--ghost btn--icon"
          title="New sequence"
          aria-label="New sequence"
          onClick={newSequence}
        >
          <PlusIcon size={15} />
        </button>
      </div>

      {isLoading && <p className="muted small">Loading sequences…</p>}

      <div className="row">
        <div className="field field--grow">
          <label className="label">Name</label>
          <input
            className="input"
            value={name}
            placeholder="e.g. Ubiquitin"
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="label">Kind</label>
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="field">
        <div className="row row--between">
          <label className="label">Residues</label>
          <button
            className="btn btn--link"
            onClick={() => {
              setDraft(DEMO_SEQUENCE);
              if (!name.trim()) setName("Ubiquitin (demo)");
            }}
          >
            Load demo
          </button>
        </div>
        <textarea
          className="input input--mono textarea"
          value={draft}
          spellCheck={false}
          placeholder="Paste or type single-letter residues (FASTA headers are ignored)…"
          onChange={(e) => setDraft(e.target.value)}
          rows={4}
        />
        <div className="row row--between small">
          <span className={validation.ok ? "muted" : "text-error"}>
            {validation.error ?? `${validation.cleaned.length} residues · valid`}
          </span>
        </div>
      </div>

      {validation.ok && rows.length > 0 && (
        <div className="ruler">
          {rows.map((row, ri) => (
            <div className="ruler__row" key={ri}>
              <span className="ruler__pos">{row[0].start}</span>
              <code className="ruler__seq">
                {row.map((c, ci) => (
                  <span className="ruler__chunk" key={ci}>
                    {c.residues}
                  </span>
                ))}
              </code>
            </div>
          ))}
        </div>
      )}

      <div className="row row--between">
        <button
          className="btn btn--primary"
          disabled={!validation.ok || !isDirty || saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? "Saving…" : selectedId == null ? "Create" : "Save"}
        </button>
        {selectedId != null && (
          <button
            className="btn btn--danger-ghost"
            disabled={deleteMutation.isPending}
            onClick={() => deleteMutation.mutate(selectedId)}
          >
            Delete
          </button>
        )}
      </div>

      {saveMutation.isError && (
        <p className="text-error small">{String((saveMutation.error as Error).message)}</p>
      )}
    </div>
  );
}
