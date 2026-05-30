import { useCallback, useEffect } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useGraphStore } from '../../stores/graphStore.js';
import FileNode from './FileNode.jsx';
import ColumnNode from './ColumnNode.jsx';
import RelationshipEdge from './RelationshipEdge.jsx';
import GraphControls from './GraphControls.jsx';

const nodeTypes = {
  fileNode: FileNode,
  columnNode: ColumnNode
};

const edgeTypes = {
  relationship: RelationshipEdge
};

const GraphCanvas = () => {
  const nodes = useGraphStore(state => state.nodes);
  const filteredEdges = useGraphStore(state => state.filteredEdges);
  const selectRelationship = useGraphStore(state => state.actions.selectRelationship);

  const [nodesState, setNodes, onNodesChange] = useNodesState(nodes);
  const [edgesState, setEdges, onEdgesChange] = useEdgesState(filteredEdges);

  // Sync edges state when filteredEdges changes in store
  useEffect(() => {
    setEdges(filteredEdges);
  }, [filteredEdges, setEdges]);

  // Sync nodes state when nodes changes in store
  useEffect(() => {
    setNodes(nodes);
  }, [nodes, setNodes]);

  const onEdgeClick = useCallback((event, edge) => {
    event.preventDefault();
  }, []);

  const onNodeClick = useCallback((_event, node) => {
    // Relationships are no longer clicked to view details for Tableau migrations
  }, []);

  if (nodes.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
        <div className="text-center">
          <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="text-gray-600 text-lg font-medium">No relationships found</p>
          <p className="text-gray-500 text-sm mt-2">Upload Excel files to discover relationships</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-gray-50 rounded-lg overflow-hidden border border-gray-200 relative">
      <ReactFlow
        nodes={nodesState}
        edges={edgesState}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onEdgeClick={onEdgeClick}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{
          padding: 0.2,
          minZoom: 0.5,
          maxZoom: 1.5
        }}
        attributionPosition="bottom-left"
        minZoom={0.3}
        maxZoom={2}
      >
        <Background
          color="#cbd5e1"
          gap={16}
          size={1}
          variant="dots"
        />
        <Controls
          showInteractive={false}
          className="!bg-white !border-gray-300 !shadow-lg"
        />
        <MiniMap
          nodeColor={(node) => {
            if (node.type === 'fileNode') return '#3b82f6';
            return '#e0e7ff';
          }}
          maskColor="rgba(0, 0, 0, 0.1)"
          className="!bg-white !border-gray-300"
        />
      </ReactFlow>

      {/* Custom Graph Controls */}
      <GraphControls />
    </div>
  );
};

const GraphCanvasWrapper = () => (
  <ReactFlowProvider>
    <GraphCanvas />
  </ReactFlowProvider>
);

export default GraphCanvasWrapper;
