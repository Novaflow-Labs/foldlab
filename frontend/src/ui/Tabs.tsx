// Segmented tab control with a sliding accent indicator. Generic over the tab
// key type so the caller keeps its own union (e.g. LeftTab). Presentation-only.

interface TabItem<K extends string> {
  key: K;
  label: string;
}

interface TabsProps<K extends string> {
  tabs: TabItem<K>[];
  active: K;
  onChange: (key: K) => void;
}

export function Tabs<K extends string>({ tabs, active, onChange }: TabsProps<K>) {
  const activeIndex = Math.max(0, tabs.findIndex((t) => t.key === active));
  const widthPct = 100 / tabs.length;

  return (
    <div className="tabs" role="tablist">
      <span
        className="tabs__indicator"
        aria-hidden
        style={{ width: `${widthPct}%`, transform: `translateX(${activeIndex * 100}%)` }}
      />
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          className={`tab ${active === t.key ? "is-active" : ""}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
