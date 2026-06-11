// Elegant score pills with semantic color + a tiny inline confidence bar.
// Presentation-only — driven entirely by scoreReadouts() data.
import { scoreReadouts } from "./score";
import type { FoldJob } from "../types";

interface ScoreChipsProps {
  job: FoldJob;
  /** "lg" = floating viewer card; "sm" = compact gallery card. */
  size?: "lg" | "sm";
}

export function ScoreChips({ job, size = "lg" }: ScoreChipsProps) {
  const readouts = scoreReadouts(job);
  if (readouts.length === 0) return null;

  return (
    <div className={`scorechips scorechips--${size}`}>
      {readouts.map((r) => (
        <span key={r.key} className={`scorechip scorechip--${r.tone}`} title={`${r.key} ${r.value}`}>
          <span className="scorechip__key">{r.key}</span>
          <span className="scorechip__val">{r.value}</span>
          {r.fill != null && (
            <span className="scorechip__bar" aria-hidden>
              <span className="scorechip__barfill" style={{ width: `${Math.round(r.fill * 100)}%` }} />
            </span>
          )}
        </span>
      ))}
    </div>
  );
}
