/**
 * API Response Validator
 * Validates that the backend response matches frontend expectations
 * Logs warnings for mismatches to help with debugging
 */

/**
 * Validate column structure
 */
const validateColumn = (column, fileIndex, colIndex) => {
  const warnings = [];

  // Check for column_name or name
  if (!column.column_name && !column.name) {
    warnings.push(`File[${fileIndex}].columns[${colIndex}]: Missing both 'column_name' and 'name' fields`);
  }

  // Check for data type
  if (!column.data_type) {
    warnings.push(`File[${fileIndex}].columns[${colIndex}]: Missing 'data_type' field`);
  }

  // Check for key indicators
  if (column.is_primary_key === undefined && !column.key_features?.primary_key_candidate) {
    warnings.push(`File[${fileIndex}].columns[${colIndex}]: Missing 'is_primary_key' field (optional but recommended)`);
  }

  if (column.is_foreign_key === undefined && !column.key_features?.foreign_key_candidate) {
    warnings.push(`File[${fileIndex}].columns[${colIndex}]: Missing 'is_foreign_key' field (optional but recommended)`);
  }

  return warnings;
};

/**
 * Validate file structure
 */
const validateFile = (file, fileIndex) => {
  const warnings = [];

  // Check required fields
  if (!file.file_name) {
    warnings.push(`File[${fileIndex}]: Missing 'file_name' field`);
  }

  if (file.row_count === undefined) {
    warnings.push(`File[${fileIndex}]: Missing 'row_count' field`);
  }

  if (file.column_count === undefined) {
    warnings.push(`File[${fileIndex}]: Missing 'column_count' field`);
  }

  // Check columns array
  if (!file.columns || !Array.isArray(file.columns)) {
    warnings.push(`File[${fileIndex}]: Missing or invalid 'columns' array`);
  } else {
    // Validate each column
    file.columns.forEach((column, colIndex) => {
      warnings.push(...validateColumn(column, fileIndex, colIndex));

      // Check for row_count consistency
      if (column.row_count !== undefined && column.row_count !== file.row_count) {
        warnings.push(
          `File[${fileIndex}].columns[${colIndex}]: Inconsistent row_count (column: ${column.row_count}, file: ${file.row_count})`
        );
      }
    });

    // Check column count matches
    if (file.columns.length !== file.column_count) {
      warnings.push(
        `File[${fileIndex}]: Column count mismatch (columns array: ${file.columns.length}, column_count: ${file.column_count})`
      );
    }
  }

  return warnings;
};

/**
 * Validate business_insights structure
 */
const validateBusinessInsights = (insights, relationshipId) => {
  const warnings = [];

  if (!insights) {
    warnings.push(`Relationship[${relationshipId}]: Missing 'business_insights'`);
    return warnings;
  }

  // Check relationship_validity
  if (!insights.relationship_validity) {
    warnings.push(`Relationship[${relationshipId}]: Missing 'business_insights.relationship_validity'`);
  } else if (!insights.relationship_validity.is_valid === undefined) {
    warnings.push(`Relationship[${relationshipId}]: Missing 'business_insights.relationship_validity.is_valid'`);
  }

  // Check decision_making_value structure
  if (insights.decision_making_value === undefined) {
    warnings.push(`Relationship[${relationshipId}]: Missing 'business_insights.decision_making_value'`);
  } else if (typeof insights.decision_making_value === 'boolean') {
    warnings.push(
      `Relationship[${relationshipId}]: 'decision_making_value' should be an object with 'can_decision_makers_act' and 'specific_actions_enabled', not a boolean`
    );
  } else if (typeof insights.decision_making_value === 'object') {
    if (insights.decision_making_value.can_decision_makers_act === undefined) {
      warnings.push(`Relationship[${relationshipId}]: Missing 'business_insights.decision_making_value.can_decision_makers_act'`);
    }
    if (!insights.decision_making_value.specific_actions_enabled) {
      warnings.push(`Relationship[${relationshipId}]: Missing 'business_insights.decision_making_value.specific_actions_enabled'`);
    }
  }

  // Check for what_story_it_tells
  if (!insights.what_story_it_tells) {
    warnings.push(`Relationship[${relationshipId}]: Missing 'business_insights.what_story_it_tells' (recommended)`);
  }

  // Check for critical_insights_revealed
  if (!insights.critical_insights_revealed || !Array.isArray(insights.critical_insights_revealed)) {
    warnings.push(`Relationship[${relationshipId}]: Missing or invalid 'business_insights.critical_insights_revealed' array`);
  }

  // Check for answerable_questions
  if (!insights.answerable_questions || !Array.isArray(insights.answerable_questions)) {
    warnings.push(`Relationship[${relationshipId}]: Missing or invalid 'business_insights.answerable_questions' array`);
  }

  return warnings;
};

/**
 * Validate relationship structure
 */
const validateRelationship = (rel, relIndex, files) => {
  const warnings = [];
  const relId = rel.relationship_id || `index_${relIndex}`;

  // Check required fields
  if (!rel.relationship_id) {
    warnings.push(`Relationship[${relIndex}]: Missing 'relationship_id'`);
  }

  if (!rel.source || !rel.source.file || !rel.source.column) {
    warnings.push(`Relationship[${relId}]: Missing or invalid 'source' (file/column)`);
  }

  if (!rel.target || !rel.target.file || !rel.target.column) {
    warnings.push(`Relationship[${relId}]: Missing or invalid 'target' (file/column)`);
  }

  // Validate file references exist
  if (rel.source?.file) {
    const fileExists = files.some(f => f.file_name === rel.source.file);
    if (!fileExists) {
      warnings.push(`Relationship[${relId}]: Source file "${rel.source.file}" not found in files array`);
    }
  }

  if (rel.target?.file) {
    const fileExists = files.some(f => f.file_name === rel.target.file);
    if (!fileExists) {
      warnings.push(`Relationship[${relId}]: Target file "${rel.target.file}" not found in files array`);
    }
  }

  // Check statistics
  if (!rel.statistics) {
    warnings.push(`Relationship[${relId}]: Missing 'statistics'`);
  } else {
    // Check for data_quality_warnings in statistics (not at root level)
    if (rel.statistics.data_quality_warnings === undefined) {
      if (rel.data_quality_concerns !== undefined) {
        warnings.push(
          `Relationship[${relId}]: 'data_quality_concerns' should be in 'statistics.data_quality_warnings', not at root level`
        );
      }
    }
  }

  // Validate business insights
  warnings.push(...validateBusinessInsights(rel.business_insights, relId));

  return warnings;
};

/**
 * Main validation function
 * Returns object with validation results and warnings
 */
export const validateApiResponse = (apiResponse) => {
  const warnings = [];

  if (!apiResponse) {
    return { isValid: false, warnings: ['API response is null or undefined'] };
  }

  const result = apiResponse.result || apiResponse;

  // Validate result structure
  if (!result) {
    return { isValid: false, warnings: ['Missing result object'] };
  }

  // Validate files
  if (!result.files || !Array.isArray(result.files)) {
    warnings.push('Missing or invalid files array');
  } else {
    result.files.forEach((file, fileIndex) => {
      warnings.push(...validateFile(file, fileIndex));
    });
  }

  // Validate relationships
  if (!result.relationships || !Array.isArray(result.relationships)) {
    warnings.push('Missing or invalid relationships array');
  } else {
    result.relationships.forEach((rel, relIndex) => {
      warnings.push(...validateRelationship(rel, relIndex, result.files || []));
    });
  }

  return {
    isValid: warnings.length === 0,
    warnings,
    summary: {
      totalFiles: result.files?.length || 0,
      totalRelationships: result.relationships?.length || 0,
      warningCount: warnings.length
    }
  };
};

/**
 * Log validation results to console
 */
export const logValidationResults = (validationResults) => {
  if (validationResults.isValid) {
    console.log('✅ API Response validation passed!');
    console.log('Summary:', validationResults.summary);
  } else {
    console.warn('⚠️ API Response validation found issues:');
    console.warn('Summary:', validationResults.summary);
    console.group('Warnings:');
    validationResults.warnings.forEach((warning, idx) => {
      console.warn(`${idx + 1}. ${warning}`);
    });
    console.groupEnd();
  }
};

/**
 * Validate and log in one call
 */
export const validateAndLog = (apiResponse) => {
  const results = validateApiResponse(apiResponse);
  logValidationResults(results);
  return results;
};
