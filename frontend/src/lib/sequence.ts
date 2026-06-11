// Amino-acid utilities: validation + position-ruler rendering.

/** The 20 canonical amino acids (single-letter codes). */
export const AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY";
const AA_SET = new Set(AMINO_ACIDS.split(""));

export interface ValidationResult {
  ok: boolean;
  cleaned: string;
  error: string | null;
}

/**
 * Validate a pasted/typed sequence. Strips whitespace, digits, and FASTA-style
 * header lines, upper-cases, and rejects any non-canonical residue.
 */
export function validateSequence(input: string): ValidationResult {
  if (input == null) return { ok: false, cleaned: "", error: "Empty sequence." };

  // Drop FASTA header lines (lines beginning with ">").
  const body = input
    .split(/\r?\n/)
    .filter((line) => !line.trimStart().startsWith(">"))
    .join("");

  // Remove whitespace, digits, and common separators.
  const cleaned = body.replace(/[\s\d\-*.]/g, "").toUpperCase();

  if (cleaned.length === 0) {
    return { ok: false, cleaned: "", error: "Empty sequence." };
  }

  const bad = new Set<string>();
  for (const ch of cleaned) {
    if (!AA_SET.has(ch)) bad.add(ch);
  }
  if (bad.size > 0) {
    return {
      ok: false,
      cleaned,
      error: `Invalid residue(s): ${[...bad].join(", ")}. Allowed: ${AMINO_ACIDS}.`,
    };
  }

  return { ok: true, cleaned, error: null };
}

export interface SequenceChunk {
  /** 1-indexed position of the first residue in this chunk. */
  start: number;
  /** Residues in this chunk (up to `size`). */
  residues: string;
}

/**
 * Split a sequence into fixed-size chunks (default 10) for a position ruler.
 * Each chunk carries its 1-indexed start position.
 */
export function chunkSequence(residues: string, size = 10): SequenceChunk[] {
  const chunks: SequenceChunk[] = [];
  for (let i = 0; i < residues.length; i += size) {
    chunks.push({ start: i + 1, residues: residues.slice(i, i + size) });
  }
  return chunks;
}

/** Group chunks into rows for display (default 5 chunks => 50 residues per row). */
export function rulerRows(residues: string, chunksPerRow = 5, chunkSize = 10): SequenceChunk[][] {
  const chunks = chunkSequence(residues, chunkSize);
  const rows: SequenceChunk[][] = [];
  for (let i = 0; i < chunks.length; i += chunksPerRow) {
    rows.push(chunks.slice(i, i + chunksPerRow));
  }
  return rows;
}

/** A short demo protein (ubiquitin, 76 aa) for the "load demo" affordance. */
export const DEMO_SEQUENCE =
  "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG";
