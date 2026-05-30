/**
 * Logic Graph Canvas - Visualize calculation dependencies using ReactFlow
 */
import { useCallback, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

import Card from '../common/Card';

// Custom node component for calculations
function CalculationNode({ data }) {
  return (
    <div
      className="px-4 py-3 rounded-lg border-2 shadow-lg min-w-[200px]"
      style={{
        backgroundColor: data.background || '#f59e0b',
        borderColor: data.isLOD ? '#8b5cf6' : '#d1d5db',
        color: 'white',
      }}
    >
      <div className="font-semibold mb-1">{data.label}</div>
      {data.formula && (
        <div className="text-xs opacity-90 truncate max-w-[180px]">
          {data.formula}
        </div>
      )}
      <div className="text-xs opacity-75 mt-1">
        {data.calcType} • Level {data.level}
      </div>
    </div>
  );
}

const nodeTypes = {
  calculationNode: CalculationNode,
};

export default function LogicGraphCanvas({ graph, onNodeClick }) {
  const initialNodes = useMemo(() => {
    if (!graph || !graph.nodes) return [];
    return graph.nodes;
  }, [graph]);

  const initialEdges = useMemo(() => {
    if (!graph || !graph.edges) return [];
    return graph.edges;
  }, [graph]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const handleNodeClick = useCallback(
    (event, node) => {
      if (onNodeClick) {
        onNodeClick(node.id);
      }
    },
    [onNodeClick]
  );

  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return (
      <Card className="h-full flex items-center justify-center">
        <div className="text-center text-gray-500">
          <p className="text-lg font-medium mb-2">No logic graph available</p>
          <p className="text-sm">
            The logic graph will appear here once calculations are analyzed.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className="w-full h-full bg-white rounded-lg border border-gray-200">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Background color="#e5e7eb" gap={16} />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            if (node.data.isLOD) return '#8b5cf6'; // purple for LOD
            if (node.data.calcType === 'MEASURE') return '#f59e0b'; // orange
            return '#3b82f6'; // blue
          }}
          maskColor="rgba(0, 0, 0, 0.1)"
        />
      </ReactFlow>
    </div>
  );
}
