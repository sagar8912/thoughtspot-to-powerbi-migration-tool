import { create } from 'zustand';

export const useGraphStore = create((set) => ({
  // Graph data
  nodes: [],
  edges: [],
  filteredEdges: [],

  // Filter state - All levels visible by default
  confidenceFilter: {
    HIGH: { visible: true, count: 0 },
    MEDIUM: { visible: true, count: 0 },
    LOW: { visible: true, count: 0 }
  },

  // Inclusion filter - Show/hide included and excluded relationships
  inclusionFilter: {
    included: { visible: true, count: 0 },
    excluded: { visible: true, count: 0 }
  },

  // Relationship inclusion state - Maps relationship_id -> { included: boolean }
  // All relationships are included by default
  relationshipInclusion: {},

  // Selected relationship for modal
  selectedRelationship: null,

  // Actions
  actions: {
    setGraphData: (apiResult) => {
      // This will be populated by graphTransform
      set({ nodes: [], edges: [], filteredEdges: [] });
    },

    toggleConfidenceLevel: (level) => {
      set((state) => {
        const newVisible = !state.confidenceFilter[level].visible;

        // Recalculate filtered edges (considering confidence filter, inclusion state, AND inclusion filter)
        const filteredEdges = state.edges.filter(edge => {
          const edgeLevel = edge.data?.confidenceLevel;
          const relationshipId = edge.data?.relationship?.relationship_id;

          // Check if relationship is excluded
          const isIncluded = state.relationshipInclusion[relationshipId]?.included !== false;

          // Check inclusion filter visibility
          const inclusionFilterVisible = isIncluded
            ? state.inclusionFilter.included.visible
            : state.inclusionFilter.excluded.visible;

          if (edgeLevel === level) return newVisible && inclusionFilterVisible;
          return state.confidenceFilter[edgeLevel]?.visible && inclusionFilterVisible;
        });

        return {
          confidenceFilter: {
            ...state.confidenceFilter,
            [level]: { ...state.confidenceFilter[level], visible: newVisible }
          },
          filteredEdges
        };
      });
    },

    toggleInclusionFilter: (type) => {
      set((state) => {
        const newVisible = !state.inclusionFilter[type].visible;

        // Recalculate filtered edges
        const filteredEdges = state.edges.filter(edge => {
          const edgeLevel = edge.data?.confidenceLevel;
          const relationshipId = edge.data?.relationship?.relationship_id;
          const isIncluded = state.relationshipInclusion[relationshipId]?.included !== false;

          // Check confidence filter
          const confidenceVisible = state.confidenceFilter[edgeLevel]?.visible;

          // Check inclusion filter
          let inclusionVisible;
          if (type === 'included' && isIncluded) {
            inclusionVisible = newVisible;
          } else if (type === 'excluded' && !isIncluded) {
            inclusionVisible = newVisible;
          } else {
            inclusionVisible = isIncluded
              ? state.inclusionFilter.included.visible
              : state.inclusionFilter.excluded.visible;
          }

          return confidenceVisible && inclusionVisible;
        });

        return {
          inclusionFilter: {
            ...state.inclusionFilter,
            [type]: { ...state.inclusionFilter[type], visible: newVisible }
          },
          filteredEdges
        };
      });
    },

    toggleRelationshipInclusion: (relationshipId) => {
      set((state) => {
        const currentState = state.relationshipInclusion[relationshipId];
        const newIncluded = !(currentState?.included !== false); // Toggle: if undefined/true -> false, if false -> true

        // Update inclusion state
        const newRelationshipInclusion = {
          ...state.relationshipInclusion,
          [relationshipId]: { included: newIncluded }
        };

        // Recalculate filtered edges (considering confidence filter AND inclusion filter)
        const filteredEdges = state.edges.filter(edge => {
          const edgeLevel = edge.data?.confidenceLevel;
          const edgeRelId = edge.data?.relationship?.relationship_id;
          const isIncluded = newRelationshipInclusion[edgeRelId]?.included !== false;

          const confidenceVisible = state.confidenceFilter[edgeLevel]?.visible;
          const inclusionVisible = isIncluded
            ? state.inclusionFilter.included.visible
            : state.inclusionFilter.excluded.visible;

          return confidenceVisible && inclusionVisible;
        });

        // Update inclusion filter counts
        const includedCount = Object.values(newRelationshipInclusion).filter(r => r.included !== false).length;
        const excludedCount = Object.values(newRelationshipInclusion).filter(r => r.included === false).length;

        return {
          relationshipInclusion: newRelationshipInclusion,
          filteredEdges,
          inclusionFilter: {
            included: { ...state.inclusionFilter.included, count: includedCount },
            excluded: { ...state.inclusionFilter.excluded, count: excludedCount }
          }
        };
      });
    },

    selectRelationship: (relationship) => {
      set({ selectedRelationship: relationship });
    },

    closeRelationshipModal: () => {
      set({ selectedRelationship: null });
    },

    exportFilteredData: () => {
      // Will implement in Phase 7
      return null;
    }
  }
}));
