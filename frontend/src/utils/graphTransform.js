/**
 * Transform API response to ReactFlow-compatible graph format
 * Creates nested nodes (files contain columns) and edges for relationships
 * @param {object} apiResult - API response containing files and relationships
 * @param {object} relationshipInclusion - Map of relationship_id -> { included: boolean }
 */

import { extractOriginalFilename } from './fileUtils.js';

export const transformToReactFlow = (apiResult, relationshipInclusion = {}) => {
  const nodes = [];
  const edges = [];

  if (!apiResult || !apiResult.result || !apiResult.result.files) {
    return { nodes, edges };
  }

  const files = apiResult.result.files;
  const relationships = apiResult.result.relationships || [];

  // Filter out deleted relationships
  const activeRelationships = relationships.filter(r => !r.deleted);

  // Step 1: Create file nodes (parent containers)
  files.forEach((file, fileIndex) => {
    const fileNode = {
      id: `file-${fileIndex}`,
      type: 'fileNode',
      data: {
        label: extractOriginalFilename(file.file_name),
        sheet: file.sheet_name,
        rowCount: file.row_count,
        columnCount: file.column_count,
        columns: file.columns || []
      },
      position: { x: fileIndex * 400, y: 0 },
      style: {
        width: 320,
        backgroundColor: '#f0f4f8',
        border: '2px solid #3b82f6',
        borderRadius: '8px',
        padding: '16px'
      }
    };
    nodes.push(fileNode);

    // Step 2: Create column nodes (children of file node)
    if (file.columns && Array.isArray(file.columns)) {
      file.columns.forEach((column, colIndex) => {
        // Support both column_name (fixed backend) and name (legacy)
        const columnName = column.column_name || column.name;

        const columnNode = {
          id: `file-${fileIndex}-col-${colIndex}`,
          type: 'columnNode',
          data: {
            label: columnName,
            dataType: column.data_type || 'unknown',
            isPrimaryKey: column.is_primary_key || false,
            isForeignKey: column.is_foreign_key || false,
            fileIndex,
            colIndex
          },
          parentNode: `file-${fileIndex}`,
          extent: 'parent',
          position: { x: 10, y: 70 + (colIndex * 45) },
          style: {
            width: 280,
            backgroundColor: column.is_primary_key ? '#fef3c7' : '#e0e7ff',
            border: '1px solid #94a3b8',
            borderRadius: '6px'
          }
        };
        nodes.push(columnNode);
      });
    }
  });

  // Step 3: Create edges from relationships
  activeRelationships.forEach((rel, relIndex) => {
    // Find source and target file indices
    // Match by either file_name or file_path (relationships use full path)
    const sourceFileIndex = files.findIndex(f =>
      f.file_name === rel.source?.file || f.file_path === rel.source?.file
    );
    const targetFileIndex = files.findIndex(f =>
      f.file_name === rel.target?.file || f.file_path === rel.target?.file
    );

    if (sourceFileIndex === -1 || targetFileIndex === -1) {
      console.warn('File not found for relationship:', rel);
      console.warn('Looking for source:', rel.source?.file);
      console.warn('Looking for target:', rel.target?.file);
      console.warn('Available files:', files.map(f => ({ name: f.file_name, path: f.file_path })));
      return;
    }

    // Find column indices
    const sourceFile = files[sourceFileIndex];
    const targetFile = files[targetFileIndex];

    const sourceColIndex = sourceFile.columns?.findIndex(
      c => (c.column_name || c.name) === rel.source?.column
    );
    const targetColIndex = targetFile.columns?.findIndex(
      c => (c.column_name || c.name) === rel.target?.column
    );

    if (sourceColIndex === -1 || targetColIndex === -1) {
      console.warn('Column not found for relationship:', rel);
      return;
    }

    // Check if relationship is excluded
    const isIncluded = relationshipInclusion[rel.relationship_id]?.included !== false;

    const edge = {
      id: `edge-${relIndex}`,
      source: `file-${sourceFileIndex}-col-${sourceColIndex}`,
      target: `file-${targetFileIndex}-col-${targetColIndex}`,
      type: 'smoothstep',
      animated: rel.confidence_level === 'HIGH' && isIncluded,
      label: `${rel.source.column} → ${rel.target.column}`,
      data: {
        relationship: rel,
        confidenceLevel: rel.confidence_level || 'MEDIUM',
        isIncluded
      },
      style: getEdgeStyle(rel.confidence_level, isIncluded),
      markerEnd: {
        type: 'arrowclosed',
        color: getEdgeColor(rel.confidence_level, isIncluded)
      }
    };
    edges.push(edge);
  });

  return { nodes, edges };
};

const getEdgeStyle = (confidenceLevel, isIncluded = true) => {
  // Base styles for excluded relationships (faded)
  if (!isIncluded) {
    return {
      stroke: '#d1d5db',
      strokeWidth: 1,
      strokeDasharray: '3,3',
      opacity: 0.4
    };
  }

  // Uniform solid style for all source relationships
  return { stroke: '#3b82f6', strokeWidth: 2 };
};

const getEdgeColor = (confidenceLevel, isIncluded = true) => {
  // Faded color for excluded relationships
  if (!isIncluded) {
    return '#d1d5db';
  }

  // Uniform normal color for all source relationships
  return '#3b82f6';
};

/**
 * Count relationships by confidence level
 */
export const countByConfidence = (edges) => {
  return edges.reduce((acc, edge) => {
    const level = edge.data?.confidenceLevel || 'MEDIUM';
    acc[level] = (acc[level] || 0) + 1;
    return acc;
  }, { HIGH: 0, MEDIUM: 0, LOW: 0 });
};
