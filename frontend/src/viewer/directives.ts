// Agent D — apply a single Directive to the loaded structure.
// Verified against molstar v4.18.0.
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";
import {
  Structure,
  StructureElement,
} from "molstar/lib/mol-model/structure";
import { EmptyLoci } from "molstar/lib/mol-model/loci";
import { MolScriptBuilder as MS } from "molstar/lib/mol-script/language/builder";
import type { Expression } from "molstar/lib/mol-script/language/expression";
import { Color } from "molstar/lib/mol-util/color";
import { setStructureOverpaint } from "molstar/lib/mol-plugin-state/helpers/structure-overpaint";
import { createStructureRepresentationParams } from "molstar/lib/mol-plugin-state/helpers/structure-representation-params";
import { StructureRepresentation3D } from "molstar/lib/mol-plugin-state/transforms/representation";

import type { Directive, DirectiveTarget } from "../types";

/** Map our representation names to Mol* built-in representation type ids. */
const REPR_MAP: Record<string, string> = {
  cartoon: "cartoon",
  "ball-and-stick": "ball-and-stick",
  surface: "molecular-surface",
  spacefill: "spacefill",
};

/**
 * Build a MolScript atomGroups expression for a directive target. Matches on
 * chain (label_asym_id) and, if present, residue / residues / residue_range
 * (label_seq_id, 1-indexed inclusive). With no fields it selects everything.
 */
function targetToExpression(target: DirectiveTarget): Expression {
  const chainTests: Expression[] = [];
  if (target.chain !== undefined) {
    chainTests.push(
      MS.core.rel.eq([
        MS.ammp("label_asym_id"),
        target.chain,
      ]),
    );
  }

  const residueTests: Expression[] = [];
  const seqId = MS.ammp("label_seq_id");
  if (target.residue !== undefined) {
    residueTests.push(MS.core.rel.eq([seqId, target.residue]));
  }
  if (target.residue_range !== undefined) {
    const [start, end] = target.residue_range;
    residueTests.push(MS.core.rel.inRange([seqId, start, end]));
  }
  if (target.residues !== undefined && target.residues.length > 0) {
    // Proven Mol* idiom for a set of seq ids: core.set.has([core.type.set(arr), prop]).
    residueTests.push(
      MS.core.set.has([MS.core.type.set(target.residues), seqId]),
    );
  }

  const args: Record<string, Expression> = {};
  if (chainTests.length > 0) {
    args["chain-test"] = MS.core.logic.and(chainTests);
  }
  if (residueTests.length === 1) {
    args["residue-test"] = residueTests[0];
  } else if (residueTests.length > 1) {
    // Multiple residue constraints (e.g. residue + range) -> OR them.
    args["residue-test"] = MS.core.logic.or(residueTests);
  }

  return MS.struct.generator.atomGroups(args);
}

/** Build a StructureElement.Loci for the target against the given structure. */
function targetToLoci(structure: Structure, target: DirectiveTarget): StructureElement.Loci {
  return StructureElement.Loci.fromExpression(structure, targetToExpression(target));
}

function currentStructureRef(plugin: PluginUIContext) {
  return plugin.managers.structure.hierarchy.current.structures[0];
}

/** Apply a single directive to the loaded structure (no-op if nothing loaded). */
export async function applyDirective(plugin: PluginUIContext, d: Directive): Promise<void> {
  const structureRef = currentStructureRef(plugin);
  const structure = structureRef?.cell.obj?.data;
  if (!structureRef || !structure) return;

  const loci = targetToLoci(structure, d.target);

  switch (d.kind) {
    case "color": {
      if (!d.color) return;
      const color = Color(parseInt(d.color.replace("#", ""), 16));
      const lociGetter = async (s: Structure) =>
        Structure.areRootsEquivalent(s, structure)
          ? loci
          : (targetToLoci(s, d.target) as StructureElement.Loci | EmptyLoci);
      await setStructureOverpaint(plugin, structureRef.components, color, lociGetter);
      return;
    }

    case "representation": {
      const type = d.repr ? REPR_MAP[d.repr] : undefined;
      if (!type) return;
      // Add a representation of the requested type for each component of the
      // structure so the whole (or targeted) structure renders in that style.
      const update = plugin.build();
      for (const component of structureRef.components) {
        update
          .to(component.cell)
          .apply(
            StructureRepresentation3D,
            createStructureRepresentationParams(plugin, structure, { type: type as never }),
          );
      }
      await update.commit();
      return;
    }

    case "focus": {
      plugin.managers.camera.focusLoci(loci);
      return;
    }

    case "select": {
      plugin.managers.structure.selection.fromLoci("set", loci);
      return;
    }

    case "label": {
      // Text labels ARE supported on this version via the measurement manager.
      await plugin.managers.structure.measurement.addLabel(loci, {
        labelParams: d.text ? { customText: d.text } : undefined,
      });
      return;
    }

    default:
      return;
  }
}
