// Display helpers for fold jobs shared by the viewer caption and result cards.
import type { FoldJob } from "../types";

/**
 * Human-readable name for a fold job. Single (non-batch) folds are created with
 * an empty label, so fall back to a stable id-based name instead of showing
 * nothing.
 */
export function jobLabel(job: FoldJob): string {
  return job.label && job.label.trim() ? job.label : `Fold #${job.id}`;
}

/** Compact local date/time for a job submission, e.g. "Jun 10, 14:32". */
export function formatJobDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
