import type { Check } from "../api";

const ICON = { pass: "✓", warn: "!", fail: "✕" } as const;
const WORD = { pass: "Passed", warn: "Caution", fail: "Failed" } as const;

export default function Checks({ checks }: { checks: Check[] }) {
  return (
    <ul className="checks">
      {checks.map((c) => (
        <li key={c.id} className={`check ${c.status}`}>
          <span className="check-icon" aria-hidden="true">{ICON[c.status]}</span>
          <div>
            <div className="check-title"><span className="sr">{WORD[c.status]}: </span>{c.label}</div>
            <div className="check-value">{c.value}</div>
            <div className="check-detail">{c.detail}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}
