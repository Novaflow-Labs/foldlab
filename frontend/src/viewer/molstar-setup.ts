// Agent D — Mol* plugin lifecycle helpers (init / load / dispose / accessors).
// Verified against molstar v4.18.0 installed in node_modules.
import { createPluginUI } from "molstar/lib/mol-plugin-ui";
import { renderReact18 } from "molstar/lib/mol-plugin-ui/react18";
import { DefaultPluginUISpec, type PluginUISpec } from "molstar/lib/mol-plugin-ui/spec";
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";
import { PluginConfig } from "molstar/lib/mol-plugin/config";
import type { Structure } from "molstar/lib/mol-model/structure";
import type { BuiltInTrajectoryFormat } from "molstar/lib/mol-plugin-state/formats/trajectory";
import { Color } from "molstar/lib/mol-util/color";

import "./viewer.css";

// Match the app's --bg ink so the WebGL canvas isn't Mol*'s default white.
const VIEWER_BG = Color(0x070a0f);

/**
 * Build a plugin spec from the defaults. We keep the default plugin (with its
 * left/right panels) but trim the always-on viewport chrome so the canvas reads
 * as an embedded viewer rather than the full Mol* app.
 */
function buildSpec(): PluginUISpec {
  const spec = DefaultPluginUISpec();
  return {
    ...spec,
    layout: {
      // Embed cleanly: collapse the left/right Mol* panels — just the canvas.
      initial: { isExpanded: false, showControls: false },
    },
    config: [
      ...(spec.config ?? []),
      [PluginConfig.Viewport.ShowExpand, false],
      [PluginConfig.Viewport.ShowControls, false],
      [PluginConfig.Viewport.ShowSettings, false],
      [PluginConfig.Viewport.ShowSelectionMode, false],
      [PluginConfig.Viewport.ShowAnimation, false],
    ],
  };
}

/** Initialise a Mol* UI plugin mounted into `container`. */
export async function initViewer(container: HTMLElement): Promise<PluginUIContext> {
  const plugin = await createPluginUI({
    target: container,
    spec: buildSpec(),
    render: renderReact18,
  });
  // Dark canvas to match the app theme (Mol*'s default renderer bg is white).
  plugin.canvas3d?.setProps({ renderer: { backgroundColor: VIEWER_BG } });
  return plugin;
}

/** Map our wire format string to a Mol* built-in trajectory format. */
function toTrajectoryFormat(format: string): BuiltInTrajectoryFormat {
  return format === "mmcif" ? "mmcif" : "pdb";
}

/**
 * Clear any loaded structures, then download + parse + apply the default
 * preset for the structure at `url`.
 */
export async function loadStructure(
  plugin: PluginUIContext,
  url: string,
  format: string,
): Promise<void> {
  await plugin.clear();
  const data = await plugin.builders.data.download(
    { url },
    { state: { isGhost: true } },
  );
  const traj = await plugin.builders.structure.parseTrajectory(
    data,
    toTrajectoryFormat(format),
  );
  await plugin.builders.structure.hierarchy.applyPreset(traj, "default");
}

/** Dispose the plugin and release its WebGL context. */
export function disposeViewer(plugin: PluginUIContext): void {
  plugin.dispose();
}

/** The current (first) loaded Structure data object, if any. */
export function getStructure(plugin: PluginUIContext): Structure | undefined {
  return plugin.managers.structure.hierarchy.current.structures[0]?.cell.obj?.data;
}
