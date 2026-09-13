// [Explainability #124]: turns one investigation's `timeline` (already
// returned by GET /api/investigations/{id} — no separate fetch) into a
// flat list of evidence-card items, one per structured `evidence_refs`
// entry across every step. Mirrors investigationToFlow.js's role for the
// Agent Collaboration Graph: a small, pure mapping layer between existing
// API data and one specific UI's shape, not a new data source.
export function flattenEvidence(timeline) {
  if (!timeline) return [];
  return timeline.flatMap((step) =>
    (step.evidence_refs || []).map((ref, index) => ({
      evidenceId: `${step.step_number}:${index}`,
      ref,
      stepNumber: step.step_number,
      agentName: step.agent_name,
      confidence: step.confidence,
      usedTools: step.used_tools || [],
      timestamp: step.timestamp,
    }))
  );
}

// A specialist can legitimately re-look-up the same order/customer more
// than once within its own tool-calling loop (e.g. a retry with a
// different query), and two specialists investigating the SAME
// cross-cutting issue (#88's fan-out) can both reference the same order
// — real, honest duplication in the underlying data, but showing the
// exact same "Order #6" card 2-3 times in one grid reads as a bug, not a
// feature. Collapses to one card per real (type, ref_id) pair, keeping
// the FIRST occurrence's evidenceId (still a valid, real address into
// evidence_refs) — nothing is deleted from the underlying data, this is
// a display-only view for the evidence grid and the drawer's navigation
// strip, both of which should agree on the same set.
export function dedupeEvidence(items) {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    const key = `${item.ref.type}:${item.ref.ref_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

// A step can carry prose `evidence` sentences with no matching
// structured `evidence_refs` entry (see _describe_evidence_refs()'s
// documented scope limits on the backend) — surfaced separately so that
// information is never silently dropped, just rendered as a plain,
// non-clickable fallback rather than a real EvidenceCard.
export function unstructuredEvidence(timeline) {
  if (!timeline) return [];
  return timeline
    .filter((step) => (step.evidence || []).length > 0 && (step.evidence_refs || []).length === 0)
    .flatMap((step) =>
      step.evidence.map((text, index) => ({
        key: `${step.step_number}-prose-${index}`,
        text,
        agentName: step.agent_name,
      }))
    );
}
