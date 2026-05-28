type Props = { hidden: boolean; onToggle: () => void };

export function TocToggle({ hidden, onToggle }: Props) {
  const label = hidden ? "Show contents" : "Hide contents";
  return (
    <button
      type="button"
      className="toc-toggle"
      aria-label={label}
      aria-pressed={hidden}
      title={label}
      onClick={onToggle}
    >
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
        <path
          d={hidden ? "M5 3l5 5-5 5" : "M11 3L6 8l5 5"}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
