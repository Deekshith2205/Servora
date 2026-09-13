// [SWARM] "Agent Collaboration Graph": React Flow wrapper replacing the
// old hand-drawn SVG SwarmGraph in AgentSwarmView.jsx. Consumes the exact
// same props the old component did (graph, revealedCount, activeStep,
// onSelectStep, liveGrowing) — AgentSwarmView.jsx itself needs no other
// change beyond swapping which component it renders.
import { useEffect, useMemo, useRef } from "react";
import { ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, useReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import AgentNode from "./AgentNode.jsx";
import { investigationToFlow } from "../utils/investigationToFlow.js";
import "./AgentCollaborationGraph.css";

const NODE_TYPES = { agentNode: AgentNode };

// Re-fits on node-count change (replay/live growth) AND on container
// resize (responsive layout — e.g. rotating a phone, or the list/detail
// grid collapsing to one column at the existing 900px breakpoint):
// React Flow's own viewport keeps whatever pan/zoom it had across a
// resize rather than re-fitting, so without this a graph fit at desktop
// width would render partly cropped after a narrower re-render.
function FitViewOnChange({ nodeCount, containerRef }) {
  const { fitView } = useReactFlow();

  useEffect(() => {
    if (nodeCount === 0) return;
    const t = setTimeout(() => fitView({ padding: 0.25, duration: 300 }), 30);
    return () => clearTimeout(t);
  }, [nodeCount, fitView]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || nodeCount === 0) return;
    const observer = new ResizeObserver(() => fitView({ padding: 0.25, duration: 200 }));
    observer.observe(el);
    return () => observer.disconnect();
  }, [containerRef, nodeCount, fitView]);

  return null;
}

function GraphInner({ graph, timeline, revealedCount, activeStep, onSelectStep, liveGrowing, containerRef }) {
  const { nodes, edges } = useMemo(
    () => investigationToFlow(graph, timeline, { revealedCount, liveGrowing, activeStep, pendingNext: liveGrowing }),
    [graph, timeline, revealedCount, liveGrowing, activeStep]
  );

  const handleNodeClick = (_event, node) => {
    if (node.data?.pending) return;
    onSelectStep?.(Number(node.id));
  };

  return (
    <>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodeClick={handleNodeClick}
        fitView
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesFocusable={false}
      >
        <Background gap={24} size={1} />
        <Controls showInteractive={false} />
        {nodes.length > 4 && <MiniMap pannable zoomable className="agent-graph-minimap" />}
      </ReactFlow>
      <FitViewOnChange nodeCount={nodes.length} containerRef={containerRef} />
    </>
  );
}

export default function AgentCollaborationGraph({ graph, timeline, revealedCount, activeStep, onSelectStep, liveGrowing, loading }) {
  const containerRef = useRef(null);

  if (loading) {
    return (
      <div className="agent-graph-state agent-graph-loading" ref={containerRef}>
        <div className="agent-graph-spinner" />
        <p>Loading investigation graph…</p>
      </div>
    );
  }

  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return (
      <div className="agent-graph-state agent-graph-empty" ref={containerRef}>
        <p>No agent activity yet.</p>
        <p className="agent-graph-empty-hint">Send a message in Customer Chat to see agents collaborate here in real time.</p>
      </div>
    );
  }

  return (
    <div className="agent-collaboration-graph" ref={containerRef}>
      <ReactFlowProvider>
        <GraphInner
          graph={graph}
          timeline={timeline}
          revealedCount={revealedCount}
          activeStep={activeStep}
          onSelectStep={onSelectStep}
          liveGrowing={liveGrowing}
          containerRef={containerRef}
        />
      </ReactFlowProvider>
    </div>
  );
}
