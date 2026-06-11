// 3-pane folding workspace. Left: sequence editor / fold controls / variant
// panel. Center: Mol* viewer (hero) + results strip. Right: chat assistant.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listProjects } from "./api/folding";
import { apiGet, structureUrl } from "./api/client";
import { ChatPanel } from "./components/ChatPanel";
import { FoldControls, useJobs } from "./components/FoldControls";
import { ResultsGallery } from "./components/ResultsGallery";
import { SequenceEditor } from "./components/SequenceEditor";
import { VariantPanel } from "./components/VariantPanel";
import { useJobsStore } from "./state/useJobsStore";
import { BrandGlyph } from "./ui/icons";
import { ScoreChips } from "./ui/ScoreChips";
import { Tabs } from "./ui/Tabs";
import { MolstarViewer } from "./viewer/MolstarViewer";

type LeftTab = "sequence" | "fold" | "variants";

const TABS: { key: LeftTab; label: string }[] = [
  { key: "sequence", label: "Sequence" },
  { key: "fold", label: "Fold" },
  { key: "variants", label: "Variants" },
];

/**
 * Optional, best-effort provider probe via the frozen apiGet helper. If the
 * backend exposes GET /api/health with a {provider} field we reflect it in the
 * top-bar pill; otherwise we silently fall back to a static "demo" pill. This
 * adds no required API surface — failures are swallowed.
 */
function useProviderMode(): string {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiGet<{ provider?: string }>("/health"),
    retry: false,
    staleTime: Infinity,
  });
  return (data?.provider ?? "demo").toLowerCase();
}

export default function App() {
  const projectId = useJobsStore((s) => s.projectId);
  const setProjectId = useJobsStore((s) => s.setProjectId);
  const selectedJobId = useJobsStore((s) => s.selectedJobId);
  const directives = useJobsStore((s) => s.directives);
  const setPickContext = useJobsStore((s) => s.setPickContext);

  const [tab, setTab] = useState<LeftTab>("sequence");

  // Resolve the active project: first project, fallback to id 1 ("Demo").
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  useEffect(() => {
    if (projects && projects.length > 0) setProjectId(projects[0].id);
  }, [projects, setProjectId]);
  const projectName = projects?.find((p) => p.id === projectId)?.name ?? "Demo";

  const providerMode = useProviderMode();
  const isLive = providerMode === "rowan";

  // Selected job → load structure only when completed and present.
  const { data: jobs = [] } = useJobs(projectId);
  const selectedJob = jobs.find((j) => j.id === selectedJobId) ?? null;
  const showStructure =
    selectedJob != null && selectedJob.state === "completed" && selectedJob.has_structure;

  return (
    <div className="app">
      <header className="app__header">
        <div className="brand">
          <span className="brand__glyph">
            <BrandGlyph size={26} />
          </span>
          <span className="brand__word">
            FOLD<span className="brand__lab">LAB</span>
          </span>
          <span className="brand__tag">Folding &amp; Design</span>
        </div>

        <div className="app__right">
          <span className="app__project">{projectName}</span>
          <span
            className={`mode-pill ${isLive ? "mode-pill--live" : ""}`}
            title={isLive ? "Live folding provider" : "Demo / mock provider"}
          >
            <span className="mode-pill__dot" />
            {providerMode}
          </span>
        </div>
      </header>

      <main className="app__main">
        <section className="panel panel--left">
          <Tabs tabs={TABS} active={tab} onChange={setTab} />
          <div className="panel__body">
            {tab === "sequence" && <SequenceEditor />}
            {tab === "fold" && <FoldControls />}
            {tab === "variants" && <VariantPanel />}
          </div>
        </section>

        <section className="panel panel--center">
          <div className="viewer-wrap">
            <MolstarViewer
              structureUrl={showStructure ? structureUrl(selectedJob!.id) : null}
              structureFormat={selectedJob?.structure_format ?? "pdb"}
              directives={directives}
              onPick={setPickContext}
            />

            {showStructure && selectedJob && (
              <div className="viewer-card">
                <div className="viewer-card__head">
                  <span className="viewer-card__label">{selectedJob.label}</span>
                  <span className="viewer-card__model">{selectedJob.model}</span>
                </div>
                <ScoreChips job={selectedJob} size="lg" />
              </div>
            )}

            {!showStructure && (
              <div className="viewer-empty">
                <span className="viewer-empty__glyph">
                  <BrandGlyph size={72} />
                </span>
                <div className="viewer-empty__title">Fold a protein to see its structure in 3D</div>
                <p className="viewer-empty__hint">
                  Pick a sequence and run a prediction from the <b>Fold</b> tab, then select a
                  completed result below.
                </p>
              </div>
            )}
          </div>
          <ResultsGallery />
        </section>

        <section className="panel panel--right">
          <ChatPanel />
        </section>
      </main>
    </div>
  );
}
