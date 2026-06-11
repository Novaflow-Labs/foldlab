// Horizontally-scrollable strip of fold-job result cards: sortable, filterable
// by batch, click-to-select. The selected job's card gets an accent ring.
import { useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";

import { jobLabel } from "../lib/jobs";
import { useJobsStore } from "../state/useJobsStore";
import type { FoldJob } from "../types";
import { CrossIcon } from "../ui/icons";
import { ScoreChips } from "../ui/ScoreChips";
import { JobBadge } from "./JobBadge";
import { useJobs } from "./FoldControls";

type SortKey = "rank_hint" | "affinity" | "iptm" | "ptm" | "confidence";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "rank_hint", label: "Rank" },
  { key: "confidence", label: "Confidence" },
  { key: "iptm", label: "ipTM" },
  { key: "ptm", label: "pTM" },
  { key: "affinity", label: "Affinity" },
];

function firstModel(job: FoldJob) {
  return job.per_model && job.per_model.length > 0 ? job.per_model[0] : null;
}

/** Pull a numeric metric from per_model first, then the flat scores map. */
function metric(job: FoldJob, key: SortKey): number | null {
  const pm = firstModel(job);
  switch (key) {
    case "rank_hint":
      return job.rank_hint ?? null;
    case "affinity":
      return pm?.affinity_pred_value ?? job.scores?.affinity_pred_value ?? null;
    case "iptm":
      return pm?.iptm ?? job.scores?.iptm ?? null;
    case "ptm":
      return pm?.ptm ?? job.scores?.ptm ?? null;
    case "confidence":
      return pm?.confidence ?? job.scores?.confidence ?? null;
  }
}

/**
 * Let a plain vertical mouse wheel scroll the single-row strip horizontally.
 * Shift+wheel and trackpad horizontal gestures already produce deltaX, so we
 * only translate when the gesture is predominantly vertical. No preventDefault:
 * nothing scrolls vertically around the strip, and it avoids React's
 * passive-listener warning.
 */
function scrollHorizontally(e: WheelEvent<HTMLDivElement>) {
  const el = e.currentTarget;
  if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
  if (el.scrollWidth <= el.clientWidth) return;
  el.scrollLeft += e.deltaY;
}

export function ResultsGallery() {
  const projectId = useJobsStore((s) => s.projectId);
  const selectedJobId = useJobsStore((s) => s.selectedJobId);
  const setSelectedJobId = useJobsStore((s) => s.setSelectedJobId);
  const activeBatchRunId = useJobsStore((s) => s.activeBatchRunId);
  const setActiveBatchRunId = useJobsStore((s) => s.setActiveBatchRunId);

  const { data: jobs = [], isLoading } = useJobs(projectId);
  const [sortKey, setSortKey] = useState<SortKey>("rank_hint");

  // Click-and-drag panning so the strip scrolls with a plain mouse. We only
  // enter drag mode once the pointer moves past a small threshold (and only when
  // the strip overflows), so a normal click still selects a card. Mouse-only —
  // touch/pen keep their native scrolling.
  const drag = useRef<{ startX: number; startLeft: number; pointerId: number; active: boolean } | null>(
    null,
  );
  // True for the click that immediately follows a drag, so we can swallow it.
  const draggedRef = useRef(false);

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    draggedRef.current = false;
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    const el = e.currentTarget;
    if (el.scrollWidth <= el.clientWidth) return; // nothing to pan
    drag.current = { startX: e.clientX, startLeft: el.scrollLeft, pointerId: e.pointerId, active: false };
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.startX;
    if (!d.active) {
      if (Math.abs(dx) < 5) return; // movement threshold — below this it's a click
      d.active = true;
      draggedRef.current = true;
      e.currentTarget.setPointerCapture(d.pointerId);
      e.currentTarget.classList.add("is-dragging");
    }
    e.currentTarget.scrollLeft = d.startLeft - dx;
  }

  function endDrag(e: PointerEvent<HTMLDivElement>) {
    const d = drag.current;
    drag.current = null;
    if (!d?.active) return;
    e.currentTarget.classList.remove("is-dragging");
    if (e.currentTarget.hasPointerCapture(d.pointerId)) {
      e.currentTarget.releasePointerCapture(d.pointerId);
    }
  }

  const visible = useMemo(() => {
    const filtered =
      activeBatchRunId != null
        ? jobs.filter((j) => j.batch_run_id === activeBatchRunId)
        : jobs;
    const sorted = [...filtered].sort((a, b) => {
      const av = metric(a, sortKey);
      const bv = metric(b, sortKey);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      // rank_hint: ascending (1 is best). Scores: descending (higher is better).
      return sortKey === "rank_hint" ? av - bv : bv - av;
    });
    return sorted;
  }, [jobs, activeBatchRunId, sortKey]);

  return (
    <div className="gallery">
      <div className="gallery__bar">
        <div className="gallery__title">
          <span className="label label--inline">Results</span>
          {!isLoading && visible.length > 0 && (
            <span className="gallery__count">{visible.length}</span>
          )}
          {activeBatchRunId != null && (
            <button
              className="chip"
              onClick={() => setActiveBatchRunId(null)}
              title="Clear batch filter"
            >
              Batch #{activeBatchRunId}
              <CrossIcon size={10} />
            </button>
          )}
        </div>
        <div className="row">
          <span className="label label--inline">Sort</span>
          <select
            className="input input--sm"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
          >
            {SORTS.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && <div className="gallery__empty">Loading jobs…</div>}
      {!isLoading && visible.length === 0 && (
        <div className="gallery__empty">No jobs yet. Fold a sequence to get started.</div>
      )}

      {!isLoading && visible.length > 0 && (
        <div
          className="gallery__strip"
          onWheel={scrollHorizontally}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          {visible.map((job, i) => {
            const selectable = job.state === "completed" && job.has_structure;
            return (
              <button
                key={job.id}
                style={{ animationDelay: `${Math.min(i, 8) * 0.03}s` }}
                className={`result ${selectedJobId === job.id ? "is-selected" : ""} ${
                  selectable ? "" : "is-disabled"
                }`}
                onClick={() => {
                  // Swallow the click that ends a drag so panning never selects.
                  if (draggedRef.current) {
                    draggedRef.current = false;
                    return;
                  }
                  if (selectable) setSelectedJobId(job.id);
                }}
                title={selectable ? "Load structure" : job.error ?? "Structure not ready"}
              >
                <div className="result__head">
                  <span className="result__label">{jobLabel(job)}</span>
                  {job.rank_hint != null && (
                    <span className="result__rank">#{job.rank_hint}</span>
                  )}
                </div>
                <div className="row row--between">
                  <JobBadge state={job.state} />
                </div>
                <ScoreChips job={job} size="sm" />
                {job.error && <div className="result__error">{job.error}</div>}
                {!job.error && scoreCount(job) === 0 && job.state === "completed" && (
                  <span className="result__placeholder">no scores reported</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Whether any score chip will render — drives the "no scores" placeholder. */
function scoreCount(job: FoldJob): number {
  const pm = firstModel(job);
  const s = job.scores ?? {};
  let n = 0;
  for (const v of [
    pm?.ptm ?? s.ptm,
    pm?.iptm ?? s.iptm,
    pm?.avg_lddt ?? s.avg_lddt,
    pm?.confidence ?? s.confidence,
    pm?.affinity_pred_value ?? s.affinity_pred_value,
    pm?.affinity_probability ?? s.affinity_probability,
  ]) {
    if (v != null) n += 1;
  }
  return n;
}
