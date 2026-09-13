// [Explainability #119]: a slim strip showing every evidence item in the
// current investigation, so a user can jump between them without closing
// the drawer — the "inspect the full explainability trail" goal applies
// across an investigation's evidence, not just one item at a time.
export default function EvidenceTimeline({ items, activeEvidenceId, onSelect }) {
  if (!items || items.length <= 1) return null;
  return (
    <div className="expl-timeline" role="tablist" aria-label="Evidence items in this investigation">
      {items.map((item) => {
        const active = item.evidenceId === activeEvidenceId;
        return (
          <button
            key={item.evidenceId}
            className={`expl-timeline-dot ${active ? "expl-timeline-dot-active" : ""}`}
            onClick={() => onSelect(item.evidenceId)}
            title={item.ref.label}
            role="tab"
            aria-selected={active}
          />
        );
      })}
    </div>
  );
}
