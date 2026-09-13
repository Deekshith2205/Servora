// [EXPLAIN] issue #97: Decision Tree visualization — deliberately distinct
// from the [SWARM] batch's Agent Swarm execution graph (issue #81): that
// graph renders steps that ACTUALLY RAN, in real dependency order. This
// tree renders the branch POINT(s) and the paths NOT taken (grayed out),
// using the same `alternatives_considered`/`chosen_action` data the
// Alternative Actions section above already has — a different question
// ("what else could have happened"), not a re-skin of the same diagram.
//
// Honest scope note, found while building this: `app/orchestrator.py`
// does NOT special-case a "clarify" decision differently from "resolve"
// today — both fall through to the same "run a specialist, then verify"
// code path (only a direct "escalate" decision short-circuits that).
// So this tree draws "resolve" and "clarify" leading to the SAME real
// second branch point (Verification), with a caption saying so, rather
// than inventing a distinct "Clarification" flow the code doesn't
// actually have.
import "./DecisionTree.css";

const ACTIONS = ["resolve", "clarify", "escalate"];

function reasonFor(action, alternatives) {
  const found = (alternatives || []).find((a) => a.action === action);
  return found ? found.rejected_because : null;
}

function ActionNode({ action, chosen, reason }) {
  return (
    <div className={`dt-node ${chosen ? "dt-node-chosen" : "dt-node-rejected"}`}>
      <div className="dt-node-title">{action}</div>
      {chosen ? (
        <div className="dt-node-badge">Taken</div>
      ) : (
        <div className="dt-node-reason">{reason || "Not chosen"}</div>
      )}
    </div>
  );
}

export default function DecisionTree({ chosenAction, alternatives, status, agentsConsulted }) {
  if (!chosenAction) return null;

  const hasVerification = (agentsConsulted || []).some((a) => a.agent_name === "verification");
  const verificationPassed = status === "resolved";

  return (
    <div className="eap-section">
      <div className="eap-section-label">Decision Tree</div>
      <div className="dt-tree">
        <div className="dt-level">
          <div className="dt-branch-label">Planner Decision</div>
          <div className="dt-row">
            {ACTIONS.map((action) => (
              <ActionNode
                key={action}
                action={action}
                chosen={action === chosenAction}
                reason={reasonFor(action, alternatives)}
              />
            ))}
          </div>
        </div>

        {hasVerification && (
          <div className="dt-level">
            <div className="dt-connector"></div>
            <div className="dt-branch-label">Verification</div>
            <div className="dt-row">
              <div className={`dt-node ${verificationPassed ? "dt-node-chosen" : "dt-node-rejected"}`}>
                <div className="dt-node-title">Pass</div>
                {verificationPassed && <div className="dt-node-badge">Taken</div>}
              </div>
              <div className={`dt-node ${!verificationPassed ? "dt-node-chosen" : "dt-node-rejected"}`}>
                <div className="dt-node-title">Fail</div>
                {!verificationPassed && <div className="dt-node-badge">Taken</div>}
              </div>
            </div>
          </div>
        )}
      </div>
      {(chosenAction === "resolve" || chosenAction === "clarify") && (
        <p className="dt-note">
          Note: today's pipeline runs the same specialist-then-verification
          path for both "resolve" and "clarify" decisions — there is no
          separate clarification flow implemented yet.
        </p>
      )}
    </div>
  );
}
