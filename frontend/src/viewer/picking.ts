// Agent D — click picking: Mol* interaction.click -> PickSelection.
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";
import { StructureElement, StructureProperties } from "molstar/lib/mol-model/structure";

import type { PickSelection } from "../types";

/**
 * Subscribe to the plugin's click behavior. When a structure element is
 * clicked, read chain/residue/resName from the first picked location and
 * forward it to `onPick`. Returns an unsubscribe function.
 */
export function subscribePick(
  plugin: PluginUIContext,
  onPick: (selection: PickSelection) => void,
): () => void {
  const sub = plugin.behaviors.interaction.click.subscribe((event) => {
    const loci = event.current.loci;
    if (!StructureElement.Loci.is(loci)) return;

    const location = StructureElement.Loci.getFirstLocation(loci);
    if (!location) return;

    const selection: PickSelection = {
      chain: StructureProperties.chain.label_asym_id(location),
      residue: StructureProperties.residue.label_seq_id(location),
      resName: StructureProperties.atom.label_comp_id(location),
    };
    onPick(selection);
  });

  return () => sub.unsubscribe();
}
