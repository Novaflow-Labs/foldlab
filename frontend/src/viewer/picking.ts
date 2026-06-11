// Agent D — click picking: Mol* interaction.click -> PickSelection.
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";
import { StructureElement, StructureProperties } from "molstar/lib/mol-model/structure";

import type { PickSelection } from "../types";

/**
 * Subscribe to the plugin's click behavior. When a structure element is
 * clicked, read chain/residue/resName from the first picked location and
 * forward it to `onPick`. When a click lands on empty space (no structure
 * element), fire `onDeselect` so callers can clear any picked-residue context.
 * Returns an unsubscribe function.
 */
export function subscribePick(
  plugin: PluginUIContext,
  onPick: (selection: PickSelection) => void,
  onDeselect: () => void,
): () => void {
  const sub = plugin.behaviors.interaction.click.subscribe((event) => {
    const loci = event.current.loci;
    if (!StructureElement.Loci.is(loci)) {
      // Clicked empty space / non-structure chrome — treat as a deselect.
      onDeselect();
      return;
    }

    const location = StructureElement.Loci.getFirstLocation(loci);
    if (!location) {
      onDeselect();
      return;
    }

    const selection: PickSelection = {
      chain: StructureProperties.chain.label_asym_id(location),
      residue: StructureProperties.residue.label_seq_id(location),
      resName: StructureProperties.atom.label_comp_id(location),
    };
    onPick(selection);
  });

  return () => sub.unsubscribe();
}
