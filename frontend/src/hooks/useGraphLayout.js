import { useCallback, useEffect } from 'react';
import { useReactFlow } from 'reactflow';

/**
 * Custom hook for graph layout management
 * Provides auto-layout functionality using simple grid layout
 * Note: For advanced layouts, install 'dagre' package
 *
 * @param {Array} nodes - ReactFlow nodes
 * @param {Array} edges - ReactFlow edges
 * @returns {Object} - Layout functions
 */
const useGraphLayout = (nodes = [], edges = []) => {
  const { setNodes, fitView } = useReactFlow();

  /**
   * Applies simple grid layout to nodes
   * This is a fallback layout when dagre is not available
   */
  const applySimpleLayout = useCallback((nodeArray, direction = 'LR') => {
    const nodeWidth = 300;
    const nodeHeight = 200;
    const horizontalGap = 400;
    const verticalGap = 250;

    // Filter parent nodes (file nodes)
    const parentNodes = nodeArray.filter(node => !node.parentNode);

    // Calculate positions based on direction
    const layoutedNodes = nodeArray.map((node) => {
      if (!node.parentNode) {
        // Parent node (file node) - calculate position
        const index = parentNodes.findIndex(n => n.id === node.id);

        let x, y;
        if (direction === 'LR') {
          // Left to right layout
          x = index * horizontalGap;
          y = 50;
        } else {
          // Top to bottom layout
          x = 50;
          y = index * verticalGap;
        }

        return {
          ...node,
          position: { x, y }
        };
      } else {
        // Child node (column node) - keep relative position within parent
        return node;
      }
    });

    return layoutedNodes;
  }, []);

  /**
   * Applies layout and updates the graph
   */
  const layoutGraph = useCallback((direction = 'LR') => {
    const layoutedNodes = applySimpleLayout(nodes, direction);
    setNodes(layoutedNodes);

    // Fit view after layout
    setTimeout(() => {
      fitView({ duration: 300, padding: 0.2 });
    }, 50);
  }, [nodes, applySimpleLayout, setNodes, fitView]);

  /**
   * Resets graph layout to default
   */
  const resetLayout = useCallback(() => {
    layoutGraph('LR');
  }, [layoutGraph]);

  /**
   * Arranges nodes horizontally
   */
  const layoutHorizontal = useCallback(() => {
    layoutGraph('LR');
  }, [layoutGraph]);

  /**
   * Arranges nodes vertically
   */
  const layoutVertical = useCallback(() => {
    layoutGraph('TB');
  }, [layoutGraph]);

  /**
   * Auto-layout on initial load
   */
  useEffect(() => {
    if (nodes.length > 0 && edges.length > 0) {
      // Apply layout on initial render
      const timer = setTimeout(() => {
        layoutGraph('LR');
      }, 100);

      return () => clearTimeout(timer);
    }
  }, [nodes.length, edges.length]); // Only run when node/edge count changes

  return {
    layoutGraph,
    resetLayout,
    layoutHorizontal,
    layoutVertical,
    applySimpleLayout
  };
};

export default useGraphLayout;
