import { useMemo } from "react";

export default function MemberChips({ suggestions, current, onPick, testId }) {
  const visible = useMemo(() => suggestions.filter((m) => m !== current), [suggestions, current]);
  if (visible.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 pt-1" data-testid={testId}>
      {visible.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onPick(m)}
          className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium hover:bg-emerald-100 active:scale-95 transition-colors"
        >
          {m}
        </button>
      ))}
    </div>
  );
}
