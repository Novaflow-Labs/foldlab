// Inline SVG icons for the FoldLab UI. Purely presentational — no logic.
// Keep these small and crisp; they inherit `currentColor` unless told otherwise.

interface IconProps {
  size?: number;
  className?: string;
}

/**
 * Brand glyph: a luminous peptide/hex node. A hexagon ring with three orbiting
 * residue nodes and a bright core — reads as "molecule" at 16–28px. The accent
 * glow is applied via CSS (filter) on the wrapping element.
 */
export function BrandGlyph({ size = 26, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M16 3.6 26.7 9.8v12.4L16 28.4 5.3 22.2V9.8L16 3.6Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
        opacity="0.55"
      />
      <path
        d="M16 9.5 16 16M16 16 10.6 19.2M16 16 21.4 19.2"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        opacity="0.85"
      />
      <circle cx="16" cy="16" r="3.1" fill="currentColor" />
      <circle cx="16" cy="9.5" r="1.9" fill="currentColor" opacity="0.9" />
      <circle cx="10.6" cy="19.2" r="1.9" fill="currentColor" opacity="0.9" />
      <circle cx="21.4" cy="19.2" r="1.9" fill="currentColor" opacity="0.9" />
    </svg>
  );
}

export function SendIcon({ size = 16, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M4.2 11.9 19.5 4.4c.7-.34 1.45.4 1.12 1.12L13.1 20.8c-.36.74-1.45.63-1.66-.17l-1.55-5.9a.9.9 0 0 0-.62-.62l-5.9-1.55c-.8-.21-.9-1.3-.17-1.66Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function CheckIcon({ size = 12, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M3.2 8.4 6.4 11.5 12.8 4.6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CrossIcon({ size = 11, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M4.5 4.5 11.5 11.5M11.5 4.5 4.5 11.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function PlusIcon({ size = 15, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M8 3.2v9.6M3.2 8h9.6"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}
