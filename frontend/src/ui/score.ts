// Shared score-extraction + formatting helpers for fold jobs. Presentation-only:
// pulls metrics from per_model first, then the flat scores map (same precedence
// the ResultsGallery has always used), and maps confidence-like values to a
// semantic tone (ok / warn / bad) for the score chips.
import type { FoldJob, PerModel } from "../types";

export type ScoreTone = "ok" | "warn" | "bad" | "info" | "neutral";

export interface ScoreReadout {
  /** Short display key, e.g. "pTM". */
  key: string;
  /** Formatted value, e.g. "0.872". */
  value: string;
  /** Raw numeric value (for bar fill + tone). */
  raw: number;
  /** Semantic tone driving chip color. */
  tone: ScoreTone;
  /** 0..1 bar fill (clamped); null hides the inline bar. */
  fill: number | null;
}

function firstModel(job: FoldJob): PerModel | null {
  return job.per_model && job.per_model.length > 0 ? job.per_model[0] : null;
}

/** confidence/pTM/ipTM live in 0..1 — map to a tier color. */
function confidenceTone(v: number): ScoreTone {
  if (v >= 0.8) return "ok";
  if (v >= 0.6) return "warn";
  return "bad";
}

/** avg_lddt may arrive as 0..1 or 0..100 — normalize for the bar + tone. */
function lddtTone(v: number): ScoreTone {
  const n = v > 1 ? v / 100 : v;
  return confidenceTone(n);
}

function fmt(n: number, digits = 3): string {
  return n.toFixed(digits);
}

/**
 * Build the ordered list of score chips for a job. Mirrors ResultsGallery's
 * precedence (per_model → scores). Affinity is rendered with the "info" tone so
 * it reads distinctly from confidence metrics.
 */
export function scoreReadouts(job: FoldJob): ScoreReadout[] {
  const pm = firstModel(job);
  const s = job.scores ?? {};
  const out: ScoreReadout[] = [];

  const ptm = pm?.ptm ?? s.ptm ?? null;
  if (ptm != null) {
    out.push({ key: "pTM", value: fmt(ptm), raw: ptm, tone: confidenceTone(ptm), fill: clamp01(ptm) });
  }

  const iptm = pm?.iptm ?? s.iptm ?? null;
  if (iptm != null) {
    out.push({ key: "ipTM", value: fmt(iptm), raw: iptm, tone: confidenceTone(iptm), fill: clamp01(iptm) });
  }

  const lddt = pm?.avg_lddt ?? s.avg_lddt ?? null;
  if (lddt != null) {
    const norm = lddt > 1 ? lddt / 100 : lddt;
    out.push({
      key: "pLDDT",
      value: lddt > 1 ? fmt(lddt, 1) : fmt(lddt),
      raw: lddt,
      tone: lddtTone(lddt),
      fill: clamp01(norm),
    });
  }

  const conf = pm?.confidence ?? s.confidence ?? null;
  if (conf != null) {
    out.push({ key: "conf", value: fmt(conf), raw: conf, tone: confidenceTone(conf), fill: clamp01(conf) });
  }

  // Affinity readouts — distinct warm/info hue, no 0..1 bar (different scale).
  const aff = pm?.affinity_pred_value ?? s.affinity_pred_value ?? null;
  if (aff != null) {
    out.push({ key: "pIC50", value: fmt(aff, 2), raw: aff, tone: "info", fill: null });
  }

  const affProb = pm?.affinity_probability ?? s.affinity_probability ?? null;
  if (affProb != null) {
    out.push({ key: "Pbind", value: fmt(affProb), raw: affProb, tone: "info", fill: clamp01(affProb) });
  }

  return out;
}

function clamp01(n: number): number {
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}
