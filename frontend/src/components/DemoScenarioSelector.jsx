import { DEMO_SCENARIOS } from "../data/demoScenarios";

export default function DemoScenarioSelector({ onSelect, disabled }) {
  return (
    <select
      className="demo-scenario-selector"
      disabled={disabled}
      value=""
      onChange={(e) => {
        const scenario = DEMO_SCENARIOS.find((s) => s.label === e.target.value);
        if (scenario) onSelect(scenario.message);
        e.target.value = "";
      }}
    >
      <option value="" disabled>
        Try a demo scenario…
      </option>
      {DEMO_SCENARIOS.map((s) => (
        <option key={s.label} value={s.label}>
          {s.label}
        </option>
      ))}
    </select>
  );
}
