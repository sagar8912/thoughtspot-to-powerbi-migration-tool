/**
 * Migration API Service - API calls for ThoughtSpot to Power BI migration
 *
 * This file keeps the same method names used by your frontend pages,
 * but maps them to your current backend endpoints.
 */

import apiClient from './api';

const normalizeMigrationResponse = (data = {}) => {
  return {
    ...data,
    migration_id: data.migration_id || data.job_id,
    job_id: data.job_id || data.migration_id,
    status: data.status || 'pending',
  };
};

const getResultData = async (migrationId) => {
  const response = await apiClient.get(`/jobs/${migrationId}/result`);
  return response.data?.result || response.data || {};
};

const downloadBlob = (blobData, fileName, mimeType = 'application/octet-stream') => {
  const blob = blobData instanceof Blob ? blobData : new Blob([blobData], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.setAttribute('download', fileName);
  document.body.appendChild(link);
  link.click();
  link.remove();

  window.URL.revokeObjectURL(url);
};

const escapeCsvValue = (value) => {
  if (value === null || value === undefined) return '';

  const text = String(value);
  const escaped = text.replace(/"/g, '""');

  if (
    escaped.includes(',') ||
    escaped.includes('"') ||
    escaped.includes('\n') ||
    escaped.includes('\r')
  ) {
    return `"${escaped}"`;
  }

  return escaped;
};

const buildConversionCsv = (conversions = [], selectedIds = null) => {
  const selectedSet =
    selectedIds && Array.from(selectedIds).length > 0
      ? new Set(Array.from(selectedIds).map(String))
      : null;

  const filteredConversions = selectedSet
    ? conversions.filter((conversion) =>
      selectedSet.has(String(conversion.conversion_id || conversion.id || ''))
    )
    : conversions;

  const headers = [
    'Conversion ID',
    'Calculation ID',
    'Source Calculated Field',
    'Source Formula',
    'Converted DAX Formula',
    'Conversion Method',
    'Confidence Score',
    'Status',
    'Warnings',
  ];

  const rows = filteredConversions.map((conversion) => {
    const warnings = Array.isArray(conversion.warnings)
      ? conversion.warnings.join('; ')
      : conversion.warnings || '';

    return [
      conversion.conversion_id || conversion.id || '',
      conversion.calc_id || conversion.calculation_id || '',
      conversion.source_calculated_field ||
      conversion.source_name ||
      conversion.calc_name ||
      conversion.name ||
      '',
      conversion.source_formula || conversion.calc_formula || conversion.formula || '',
      conversion.dax_formula ||
      conversion.converted_dax_formula ||
      conversion.target_formula ||
      '',
      conversion.conversion_method || conversion.method || '',
      conversion.confidence_score ?? '',
      conversion.status || '',
      warnings,
    ];
  });

  return [
    headers.map(escapeCsvValue).join(','),
    ...rows.map((row) => row.map(escapeCsvValue).join(',')),
  ].join('\n');
};

const migrationApi = {
  // ============================================================
  // Migration Job
  // ============================================================

  createMigration: async (files, onUploadProgress) => {
    const formData = new FormData();

    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await apiClient.post('/jobs/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onUploadProgress && progressEvent.total) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );

          onUploadProgress(percentCompleted);
        }
      },
    });

    return normalizeMigrationResponse(response.data);
  },

  getMigrationStatus: async (migrationId) => {
    const response = await apiClient.get(`/jobs/${migrationId}`);
    return normalizeMigrationResponse(response.data);
  },

  deleteMigration: async (migrationId) => {
    const response = await apiClient.delete(`/jobs/${migrationId}`);
    return response.data;
  },

  getMigrationResult: async (migrationId) => {
    const response = await apiClient.get(`/jobs/${migrationId}/result`);
    return response.data;
  },

  // ============================================================
  // Objects / Workbooks
  // ============================================================

  getWorkbooks: async (migrationId, params = {}) => {
    try {
      const response = await apiClient.get(`/migration/${migrationId}/objects`, {
        params: {
          object_type: params.object_type || undefined,
          limit: params.limit || 1000,
          offset: params.offset || 0,
        },
      });

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        objects: result.objects || result.files || [],
        workbooks: result.workbooks || result.objects || result.files || [],
        summary: result.summary || {},
      };
    }
  },

  getCalculations: async (migrationId, params = {}) => {
    try {
      const response = await apiClient.get(`/migration/${migrationId}/formulas`, {
        params: {
          limit: params.limit || 1000,
          offset: params.offset || 0,
          object_id: params.object_id || params.workbookId || undefined,
        },
      });

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        calculations: result.formulas || result.calculations || [],
        formulas: result.formulas || result.calculations || [],
        summary: result.summary || {},
      };
    }
  },

  getFormulas: async (migrationId, params = {}) => {
    try {
      const response = await apiClient.get(`/migration/${migrationId}/formulas`, {
        params: {
          limit: params.limit || 1000,
          offset: params.offset || 0,
          object_id: params.object_id || params.workbookId || undefined,
        },
      });

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        calculations: result.formulas || result.calculations || [],
        formulas: result.formulas || result.calculations || [],
        summary: result.summary || {},
      };
    }
  },

  // ============================================================
  // Logic Graph / Model
  // ============================================================

  getLogicGraph: async (migrationId, format = 'reactflow') => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/logic-graph`,
        {
          params: { format },
        }
      );

      return response.data;
    } catch (error) {
      return {
        nodes: [],
        edges: [],
        format,
        message: 'Logic graph is not available yet for this migration.',
      };
    }
  },

  // ============================================================
  // DAX Conversions
  // ============================================================

  getConversions: async (migrationId, params = {}) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/conversions`,
        {
          params: {
            limit: params.limit || 1000,
            offset: params.offset || 0,
            status: params.status || undefined,
          },
        }
      );

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        conversions: result.conversions || result.dax_conversions || [],
        summary: result.summary || {},
      };
    }
  },

  getConversion: async (migrationId, conversionId) => {
    const response = await apiClient.get(
      `/migration/${migrationId}/conversions/${conversionId}`
    );

    return response.data;
  },

  updateConversion: async (
    migrationId,
    conversionId,
    daxFormula,
    reasoning = null
  ) => {
    const response = await apiClient.patch(
      `/migration/${migrationId}/conversions/${conversionId}`,
      {
        dax_formula: daxFormula,
        reasoning: reasoning || 'Manual override by user',
      }
    );

    return response.data;
  },

  triggerConversion: async (migrationId) => {
    const response = await apiClient.post(
      `/migration/${migrationId}/trigger-conversion`
    );

    return response.data;
  },

  // ============================================================
  // Validation
  // ============================================================

  triggerValidation: async (migrationId) => {
    const response = await apiClient.post(`/migration/${migrationId}/validate`);
    return response.data;
  },

  getValidationResults: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/validation-results`
      );

      return response.data;
    } catch (error) {
      return {
        validation_results: [],
        results: [],
        summary: {
          passed: 0,
          failed: 0,
          warning: 0,
        },
      };
    }
  },

  getFidelityValidation: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/fidelity-validation`
      );

      return response.data;
    } catch (error) {
      return {
        fidelity_score: 0,
        results: [],
        message: 'Fidelity validation is not available yet.',
      };
    }
  },

  getCorrectionHistory: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/correction-history`
      );

      return response.data;
    } catch (error) {
      return {
        corrections: [],
        correction_attempts: [],
        message: 'Correction history is not available yet.',
      };
    }
  },

  getFidelityStats: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/fidelity-stats`
      );

      return response.data;
    } catch (error) {
      return {
        total_tests: 0,
        passed_tests: 0,
        failed_tests: 0,
        fidelity_score: 0,
      };
    }
  },

  // ============================================================
  // Export / Downloads
  // ============================================================

  exportPowerBI: async (migrationId) => {
    try {
      const response = await apiClient.post(`/migration/${migrationId}/export`);
      return response.data;
    } catch (error) {
      return await getResultData(migrationId);
    }
  },

  downloadArtifacts: async (migrationId) => {
    const response = await apiClient.get(`/migration/${migrationId}/download`, {
      responseType: 'blob',
    });

    return response.data;
  },

  /**
   * Corrected:
   * Backend does not currently have:
   * GET /migration/{migrationId}/conversion-report
   *
   * So this generates a CSV report from existing conversion data.
   * Excel can open this CSV file directly.
   */
  downloadConversionReport: async (migrationId, conversionIds = null) => {
    let conversions = [];

    try {
      const conversionResponse = await migrationApi.getConversions(migrationId, {
        limit: 10000,
        offset: 0,
      });

      conversions = conversionResponse.conversions || [];
    } catch (error) {
      const result = await getResultData(migrationId);
      conversions = result.conversions || result.dax_conversions || [];
    }

    const csvContent = buildConversionCsv(conversions, conversionIds);

    downloadBlob(
      csvContent,
      'thoughtspot_dax_conversion_report.csv',
      'text/csv;charset=utf-8;'
    );

    return csvContent;
  },

  downloadAllArtifacts: async (migrationId) => {
    const response = await apiClient.get(
      `/migration/${migrationId}/download-all`,
      {
        responseType: 'blob',
      }
    );

    downloadBlob(response.data, 'thoughtspot_powerbi_migration_package.zip');

    return response.data;
  },

  // ============================================================
  // Data Quality / Preview / Relationships
  // ============================================================

  getDataQuality: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/data-quality`
      );

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        checks: [],
        summary: result.summary || {},
        message:
          'Basic migration report loaded. Detailed data quality is not available yet.',
      };
    }
  },

  getDataPreview: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/data-preview`
      );

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        files: result.files || [],
        objects: result.objects || [],
        preview: [],
      };
    }
  },

  getTableClassifications: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/table-classifications`
      );

      return response.data;
    } catch (error) {
      return {
        classifications: [],
        tables: [],
        objects: [],
      };
    }
  },

  getSuggestedRelationships: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/suggested-relationships`
      );

      return response.data;
    } catch (error) {
      return {
        relationships: [],
        suggested_relationships: [],
      };
    }
  },

  getFilters: async (migrationId) => {
    try {
      const response = await apiClient.get(`/migration/${migrationId}/filters`);
      return response.data;
    } catch (error) {
      return {
        filters: [],
      };
    }
  },

  // ============================================================
  // Recommendations / Model Enhancements
  // ============================================================

  getRecommendations: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/recommendations`
      );

      return response.data;
    } catch (error) {
      return {
        recommendations: [],
        summary: {},
      };
    }
  },

  getModelEnhancements: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/model-enhancements`
      );

      return response.data;
    } catch (error) {
      return {
        required: false,
        enhancements: [],
      };
    }
  },

  downloadEnhancementGuide: async (migrationId) => {
    const response = await apiClient.get(
      `/migration/${migrationId}/model-enhancements/download`,
      {
        responseType: 'blob',
      }
    );

    downloadBlob(response.data, 'THOUGHTSPOT_POWERBI_MODEL_ENHANCEMENTS.md');

    return response.data;
  },

  downloadAllEnhancements: async (migrationId) => {
    const response = await apiClient.get(
      `/migration/${migrationId}/model-enhancements/download-all`,
      {
        responseType: 'blob',
      }
    );

    downloadBlob(response.data, 'thoughtspot_powerbi_model_enhancements.zip');

    return response.data;
  },

  // ============================================================
  // Workbook Metadata
  // ============================================================

  getWorkbookMetadataSummary: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/workbook-metadata/summary`
      );

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        summary: result.summary || {},
        object_count: result.summary?.object_count || 0,
        formula_count: result.summary?.formula_count || 0,
        relationship_count: result.summary?.relationship_count || 0,
      };
    }
  },

  getWorkbookMetadata: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/workbook-metadata`
      );

      return response.data;
    } catch (error) {
      return await getResultData(migrationId);
    }
  },

  getWorkbookWorksheets: async (migrationId, workbookId) => {
    const response = await apiClient.get(
      `/migration/${migrationId}/workbook-metadata/${workbookId}/worksheets`
    );

    return response.data;
  },

  getWorkbookCalculatedFields: async (migrationId, workbookId) => {
    const response = await apiClient.get(
      `/migration/${migrationId}/workbook-metadata/${workbookId}/calculated-fields`
    );

    return response.data;
  },

  getTableDetails: async (migrationId, workbookId, tableName) => {
    const response = await apiClient.get(
      `/migration/${migrationId}/workbook-metadata/${workbookId}/table/${tableName}`
    );

    return response.data;
  },

  getTablesData: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/workbook-metadata/tables-data`
      );

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        tables: result.tables || result.files || result.objects || [],
        objects: result.objects || result.files || [],
      };
    }
  },

  getModelIntelligence: async (migrationId) => {
    try {
      const response = await apiClient.get(
        `/migration/${migrationId}/workbook-metadata/model-intelligence`
      );

      return response.data;
    } catch (error) {
      const result = await getResultData(migrationId);

      return {
        tables: result.tables || result.files || [],
        objects: result.objects || result.files || [],
        summary: result.summary || {},
      };
    }
  },
};

export default migrationApi;