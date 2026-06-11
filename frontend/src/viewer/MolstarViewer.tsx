import { useEffect, useRef } from "react";

import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";

import type { Directive, PickSelection } from "../types";
import { applyDirective } from "./directives";
import { disposeViewer, initViewer, loadStructure } from "./molstar-setup";
import { subscribePick } from "./picking";

// Mol* dark skin (sass is installed; Vite compiles this). Confirmed path for v4.18.
import "molstar/lib/mol-plugin-ui/skin/dark.scss";
import "./viewer.css";

/**
 * FROZEN PROP INTERFACE — kept exactly as the Phase-0 placeholder declared it.
 * Agent E imports <MolstarViewer> by these props.
 */
export interface MolstarViewerProps {
  structureUrl: string | null;
  structureFormat?: string; // "pdb" | "mmcif"
  directives?: Directive[];
  onPick?: (selection: PickSelection) => void;
}

export function MolstarViewer({
  structureUrl,
  structureFormat = "pdb",
  directives,
  onPick,
}: MolstarViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pluginRef = useRef<PluginUIContext | null>(null);
  // Resolves once the plugin is initialized; effects await it so ordering holds
  // regardless of how React schedules them.
  const readyRef = useRef<Promise<PluginUIContext> | null>(null);
  // The structure key (url|format) currently loaded into the plugin, so we can
  // tell a structure change from a directives-only change.
  const loadedKeyRef = useRef<string | null>(null);
  // How many directives from the current array have already been applied to the
  // currently-loaded structure.
  const appliedCountRef = useRef(0);
  // Serializes async work so overlapping renders apply in order.
  const queueRef = useRef<Promise<unknown>>(Promise.resolve());
  // Latest onPick, read through a ref so the picking subscription is stable.
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  // Init the plugin exactly once and subscribe picking. The `disposed` guard
  // tolerates React 18 StrictMode's mount/unmount/mount in development.
  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;
    let unsubscribe: (() => void) | null = null;

    const ready = initViewer(containerRef.current).then((plugin) => {
      if (disposed) {
        // Effect was cleaned up before init finished — tear down immediately.
        disposeViewer(plugin);
        throw new Error("viewer disposed during init");
      }
      pluginRef.current = plugin;
      unsubscribe = subscribePick(plugin, (sel) => onPickRef.current?.(sel));
      return plugin;
    });
    readyRef.current = ready;
    // Swallow the rejection from the disposed-during-init path so it is not an
    // unhandled promise rejection; real init errors still surface in console.
    ready.catch((err) => {
      if (!disposed) console.error("Mol* viewer init failed", err);
    });

    return () => {
      disposed = true;
      unsubscribe?.();
      const plugin = pluginRef.current;
      pluginRef.current = null;
      readyRef.current = null;
      loadedKeyRef.current = null;
      appliedCountRef.current = 0;
      if (plugin) disposeViewer(plugin);
    };
  }, []);

  // Single coordinated effect for structure + directives. Decides per render
  // whether to (re)load the structure or just apply newly-added directives, and
  // serializes the async work so out-of-order renders can't interleave.
  useEffect(() => {
    const ready = readyRef.current;
    if (!ready) return;

    const next = directives ?? [];
    const key = structureUrl ? `${structureUrl}|${structureFormat}` : null;

    const run = queueRef.current
      .catch(() => {})
      .then(async () => {
        const plugin = pluginRef.current ?? (await ready);

        if (key === null) {
          // No structure: clear everything.
          if (loadedKeyRef.current !== null) {
            await plugin.clear();
            loadedKeyRef.current = null;
            appliedCountRef.current = 0;
          }
          return;
        }

        // Reload when the structure changed OR when the directive list shrank
        // / was replaced (we can't cheaply un-apply individual directives, so we
        // reset by reloading and reapplying the full list).
        const structureChanged = loadedKeyRef.current !== key;
        const shrankOrReplaced = next.length < appliedCountRef.current;

        if (structureChanged || shrankOrReplaced) {
          await loadStructure(plugin, structureUrl!, structureFormat);
          loadedKeyRef.current = key;
          appliedCountRef.current = 0;
        }

        // Apply directives not yet applied to the current structure.
        for (let i = appliedCountRef.current; i < next.length; i++) {
          await applyDirective(plugin, next[i]);
        }
        appliedCountRef.current = next.length;
      })
      .catch((err) => {
        console.error("Mol* viewer update failed", err);
      });

    queueRef.current = run;
  }, [structureUrl, structureFormat, directives]);

  return <div ref={containerRef} className="molstar-viewer" />;
}
