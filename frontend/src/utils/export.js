/**
 * Export utilities for downloading data as JSON files
 */

/**
 * Download data as JSON file
 */
export const exportJSON = (data, filename) => {
  try {
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
    return true;
  } catch (error) {
    console.error('Export failed:', error);
    return false;
  }
};

/**
 * Filter result data by visible edges
 */
export const filterResultsByVisibility = (fullResult, visibleEdges, confidenceFilter) => {
  if (!fullResult || !fullResult.result) {
    return null;
  }

  // Get visible relationship IDs
  const visibleRelIds = new Set(
    visibleEdges.map(edge => edge.data?.relationship?.relationship_id).filter(Boolean)
  );

  // Filter relationships
  const filteredRelationships = fullResult.result.relationships?.filter(
    rel => visibleRelIds.has(rel.relationship_id)
  ) || [];

  // Create filtered result
  const filteredResult = {
    ...fullResult,
    result: {
      ...fullResult.result,
      relationships: filteredRelationships,
      report_metadata: {
        ...fullResult.result.report_metadata,
        total_relationships_found: filteredRelationships.length,
        filtered: true,
        filters_applied: {
          confidence_levels: Object.keys(confidenceFilter)
            .filter(level => confidenceFilter[level].visible)
        }
      }
    }
  };

  return filteredResult;
};

/**
 * Generate filename with timestamp
 */
export const generateFilename = (prefix, extension = 'json') => {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
  return `${prefix}_${timestamp}.${extension}`;
};
