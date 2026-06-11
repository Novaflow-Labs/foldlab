// Global workspace state: active project, selected job, viewer directives,
// and the last picked residue (shared between the viewer and the chat panel).
import { create } from "zustand";

import type { Directive, PickSelection } from "../types";

interface JobsState {
  projectId: number;
  selectedJobId: number | null;
  /** Batch currently being inspected in the ResultsGallery (null = all jobs). */
  activeBatchRunId: number | null;
  /** Directives applied to the Mol* viewer (sourced from chat + quick actions). */
  directives: Directive[];
  /** Last residue the user picked in the viewer. */
  pickContext: PickSelection | null;

  setProjectId: (id: number) => void;
  setSelectedJobId: (id: number | null) => void;
  setActiveBatchRunId: (id: number | null) => void;
  pushDirective: (d: Directive) => void;
  setDirectives: (d: Directive[]) => void;
  clearDirectives: () => void;
  setPickContext: (p: PickSelection | null) => void;
}

export const useJobsStore = create<JobsState>()((set) => ({
  projectId: 1,
  selectedJobId: null,
  activeBatchRunId: null,
  directives: [],
  pickContext: null,

  setProjectId: (id) => set({ projectId: id }),
  setSelectedJobId: (id) => set({ selectedJobId: id }),
  setActiveBatchRunId: (id) => set({ activeBatchRunId: id }),
  pushDirective: (d) => set((s) => ({ directives: [...s.directives, d] })),
  setDirectives: (d) => set({ directives: d }),
  clearDirectives: () => set({ directives: [] }),
  setPickContext: (p) => set({ pickContext: p }),
}));
