// Small colored state pill for a fold job. Running/queued = pulsing accent
// spinner; completed = accent check; failed = bad.
import type { JobState } from "../types";
import { CheckIcon } from "../ui/icons";

const LABELS: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  stopped: "Stopped",
};

export function JobBadge({ state }: { state: JobState | string }) {
  const key = String(state).toLowerCase();
  const label = LABELS[key] ?? state;
  const spinning = key === "running" || key === "queued";
  return (
    <span className={`badge badge--${key}`}>
      {spinning && <span className="badge__spinner" aria-hidden />}
      {key === "completed" && (
        <span className="badge__check" aria-hidden>
          <CheckIcon size={11} />
        </span>
      )}
      {label}
    </span>
  );
}
