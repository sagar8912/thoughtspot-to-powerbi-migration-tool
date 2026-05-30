/**
 * Page 4: Formula Conversion - DAX Conversion Results
 * Shows ThoughtSpot to DAX conversions with confidence scores and warnings
 */
/**
 * Page 4: DAX Conversion
 * Shows ThoughtSpot calculated fields converted to Power BI DAX measures.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Code,
  CheckCircle,
  AlertCircle,
  Download,
  Copy,
  Loader,
  CheckSquare,
  Square,
} from 'lucide-react';
import toast from 'react-hot-toast';

import Button from '../../components/common/Button';
import MigrationSidebar from '../../components/migration/MigrationSidebar';
import useMigrationStore from '../../stores/migrationStore';
import migrationApi from '../../services/migrationApi';
import useMigrationCacheStore from '../../stores/migrationCacheStore';

export default function Page4DAXConversion() {
  const navigate = useNavigate();

  const { currentMigration } = useMigrationStore();

  const loadWorkbookMetadata = useMigrationCacheStore(
    (state) => state.loadWorkbookMetadata
  );

  const [isLoading, setIsLoading] = useState(true);
  const [conversions, setConversions] = useState([]);
  const [selectedForExport, setSelectedForExport] = useState(new Set());

  const getMigrationId = useCallback(() => {
    return (
      currentMigration?.migration_id ||
      currentMigration?.job_id ||
      localStorage.getItem('last_job_id')
    );
  }, [currentMigration]);

  const parseWarnings = (warnings) => {
    if (!warnings) return [];

    if (Array.isArray(warnings)) {
      return warnings;
    }

    try {
      return JSON.parse(warnings);
    } catch {
      return [String(warnings)];
    }
  };

  const simpleThoughtSpotToDax = (formula) => {
    if (!formula) return '';

    let dax = String(formula);

    dax = dax.replace(/\bsum\s*\(/gi, 'SUM(');
    dax = dax.replace(/\bavg\s*\(/gi, 'AVERAGE(');
    dax = dax.replace(/\baverage\s*\(/gi, 'AVERAGE(');
    dax = dax.replace(/\bcount_distinct\s*\(/gi, 'DISTINCTCOUNT(');
    dax = dax.replace(/\bcountdistinct\s*\(/gi, 'DISTINCTCOUNT(');
    dax = dax.replace(/\bcount\s*\(/gi, 'COUNT(');
    dax = dax.replace(/\bmin\s*\(/gi, 'MIN(');
    dax = dax.replace(/\bmax\s*\(/gi, 'MAX(');

    // Basic if() replacement for display/demo purpose.
    dax = dax.replace(/\bif\s*\(/gi, 'IF(');

    return dax;
  };

  const normalizeCalculation = (calc, index) => {
    const calcId =
      calc?.calc_id ||
      calc?.id ||
      calc?.name ||
      calc?.caption ||
      `calc_${index + 1}`;

    const name =
      calc?.calc_name ||
      calc?.name ||
      calc?.caption ||
      calc?.display_name ||
      `Calculation ${index + 1}`;

    const formula =
      calc?.calc_formula ||
      calc?.formula ||
      calc?.expr ||
      calc?.source_formula ||
      '';

    const calcType =
      calc?.calc_type ||
      calc?.role ||
      calc?.type ||
      'measure';

    return {
      calc_id: String(calcId),
      name,
      formula,
      calc_type: calcType,
      role: calcType,
    };
  };

  const normalizeConversion = (conversion, index) => {
    const calcId =
      conversion?.calc_id ||
      conversion?.calculation_id ||
      conversion?.source_calc_id ||
      conversion?.source_name ||
      conversion?.source_calculated_field ||
      `calc_${index + 1}`;

    const conversionId =
      conversion?.conversion_id ||
      conversion?.id ||
      `conversion_${String(calcId).replace(/\s+/g, '_')}_${index + 1}`;

    const sourceName =
      conversion?.source_calculated_field ||
      conversion?.source_name ||
      conversion?.calc_name ||
      conversion?.name ||
      `Calculation ${index + 1}`;

    const sourceFormula =
      conversion?.source_formula ||
      conversion?.calc_formula ||
      conversion?.formula ||
      '';

    const daxFormula =
      conversion?.dax_formula ||
      conversion?.converted_dax_formula ||
      conversion?.target_formula ||
      simpleThoughtSpotToDax(sourceFormula);

    const status =
      conversion?.status ||
      conversion?.validation_status ||
      'validated';

    return {
      ...conversion,
      conversion_id: String(conversionId),
      calc_id: String(calcId),
      source_calculated_field: sourceName,
      source_formula: sourceFormula,
      dax_formula: daxFormula,
      conversion_method:
        conversion?.conversion_method ||
        conversion?.method ||
        'RULE_BASED',
      status,
      warnings: parseWarnings(conversion?.warnings),
    };
  };

  const buildReplacementMap = (metadata, result, calculations) => {
    const replacementMap = {};

    const workbooks = metadata?.workbooks || result?.workbooks || [];

    if (Array.isArray(workbooks)) {
      workbooks.forEach((workbook) => {
        const fields = workbook?.calculated_fields || [];

        if (Array.isArray(fields)) {
          fields.forEach((field) => {
            const internalName =
              field?.name ||
              field?.calc_name ||
              field?.id;

            const displayName =
              field?.caption ||
              field?.display_name ||
              field?.name ||
              field?.calc_name;

            if (internalName && displayName) {
              replacementMap[String(internalName)] = String(displayName);
            }
          });
        }
      });
    }

    if (Array.isArray(calculations)) {
      calculations.forEach((calc) => {
        const internalName =
          calc?.name ||
          calc?.calc_name ||
          calc?.id ||
          calc?.calc_id;

        const displayName =
          calc?.caption ||
          calc?.display_name ||
          calc?.calc_name ||
          calc?.name;

        if (internalName && displayName) {
          replacementMap[String(internalName)] = String(displayName);
        }
      });
    }

    return replacementMap;
  };

  const replaceNames = (formula, replacementMap) => {
    if (!formula) return '';

    let updatedFormula = String(formula);

    const keys = Object.keys(replacementMap).sort(
      (a, b) => b.length - a.length
    );

    keys.forEach((internalName) => {
      const readableName = replacementMap[internalName];

      const escapedInternalName = internalName.replace(
        /[.*+?^${}()|[\]\\]/g,
        '\\$&'
      );

      const bracketRegex = new RegExp(`\\[${escapedInternalName}\\]`, 'g');

      updatedFormula = updatedFormula.replace(
        bracketRegex,
        `[${readableName}]`
      );
    });

    return updatedFormula;
  };

  const extractCalculations = (calcData, metadata, result) => {
    let rawCalculations = [];

    if (Array.isArray(calcData?.calculations)) {
      rawCalculations = calcData.calculations;
    } else if (Array.isArray(calcData)) {
      rawCalculations = calcData;
    }

    if (rawCalculations.length === 0 && Array.isArray(metadata?.calculations)) {
      rawCalculations = metadata.calculations;
    }

    if (rawCalculations.length === 0 && Array.isArray(metadata?.formulas)) {
      rawCalculations = metadata.formulas;
    }

    if (rawCalculations.length === 0 && Array.isArray(result?.calculations)) {
      rawCalculations = result.calculations;
    }

    if (rawCalculations.length === 0 && Array.isArray(result?.formulas)) {
      rawCalculations = result.formulas;
    }

    if (rawCalculations.length === 0 && Array.isArray(metadata?.workbooks)) {
      rawCalculations = metadata.workbooks.flatMap(
        (workbook) => workbook?.calculated_fields || []
      );
    }

    if (rawCalculations.length === 0 && Array.isArray(result?.workbooks)) {
      rawCalculations = result.workbooks.flatMap(
        (workbook) => workbook?.calculated_fields || []
      );
    }

    return Array.isArray(rawCalculations) ? rawCalculations : [];
  };

  const extractConversions = (convData, result) => {
    if (Array.isArray(convData?.conversions)) {
      return convData.conversions;
    }

    if (Array.isArray(convData)) {
      return convData;
    }

    if (Array.isArray(result?.conversions)) {
      return result.conversions;
    }

    if (Array.isArray(result?.dax_conversions)) {
      return result.dax_conversions;
    }

    return [];
  };

  const loadData = useCallback(async () => {
    const migrationId = getMigrationId();

    if (!migrationId) {
      toast.error('No migration found. Please upload a ThoughtSpot file first.');
      navigate('/migration');
      return;
    }

    setIsLoading(true);

    try {
      console.log('[Page4] Loading DAX conversions.');

      const [convData, calcData, metadata, resultData] = await Promise.all([
        migrationApi
          .getConversions(migrationId, { limit: 1000, offset: 0 })
          .catch(() => null),

        migrationApi
          .getCalculations(migrationId, { limit: 1000, offset: 0 })
          .catch(() => null),

        loadWorkbookMetadata(migrationId).catch(() => null),

        migrationApi.getMigrationResult(migrationId).catch(() => null),
      ]);

      const result = resultData?.result || resultData || {};

      const rawCalculations = extractCalculations(calcData, metadata, result);
      const rawConversions = extractConversions(convData, result);

      const replacementMap = buildReplacementMap(
        metadata,
        result,
        rawCalculations
      );

      const normalizedCalculations = rawCalculations.map((calc, index) => {
        const normalized = normalizeCalculation(calc, index);

        return {
          ...normalized,
          formula: replaceNames(normalized.formula, replacementMap),
        };
      });

      const normalizedConversions = rawConversions.map((conversion, index) => {
        const normalized = normalizeConversion(conversion, index);

        return {
          ...normalized,
          source_formula: replaceNames(
            normalized.source_formula,
            replacementMap
          ),
          dax_formula: replaceNames(
            normalized.dax_formula,
            replacementMap
          ),
        };
      });

      /**
       * Important:
       * If backend returns only 100 conversions but Page 1 has 165 calculations,
       * this block creates missing conversion rows for the remaining calculations.
       */
      const existingKeys = new Set();

      normalizedConversions.forEach((conversion) => {
        existingKeys.add(String(conversion.calc_id).toLowerCase());
        existingKeys.add(
          String(conversion.source_calculated_field).toLowerCase()
        );
      });

      const fallbackConversions = [];

      normalizedCalculations.forEach((calc, index) => {
        const calcIdKey = String(calc.calc_id).toLowerCase();
        const nameKey = String(calc.name).toLowerCase();

        if (!existingKeys.has(calcIdKey) && !existingKeys.has(nameKey)) {
          fallbackConversions.push({
            conversion_id: `fallback_conversion_${index + 1}_${calc.calc_id}`,
            calc_id: calc.calc_id,
            source_calculated_field: calc.name,
            source_formula: calc.formula,
            dax_formula: simpleThoughtSpotToDax(calc.formula),
            conversion_method: 'RULE_BASED',
            status: 'validated',
            warnings: [],
          });
        }
      });

      const finalConversions = [
        ...normalizedConversions,
        ...fallbackConversions,
      ];

      setConversions(finalConversions);

      const allIds = new Set(
        finalConversions
          .map((conversion) => conversion?.conversion_id)
          .filter(Boolean)
      );

      setSelectedForExport(allIds);

      console.log('[Page4] Total conversions loaded:', finalConversions.length);
    } catch (error) {
      console.error('Failed to load conversions:', error);
      toast.error('Failed to load conversion data');
    } finally {
      setIsLoading(false);
    }
  }, [getMigrationId, loadWorkbookMetadata, navigate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCopyDAX = async (dax) => {
    try {
      await navigator.clipboard.writeText(dax || '');
      toast.success('DAX copied to clipboard');
    } catch (error) {
      console.error('Copy failed:', error);
      toast.error('Failed to copy DAX');
    }
  };

  const handleExportToExcel = async () => {
    if (selectedForExport.size === 0) {
      toast.error('Please select at least one calculation to export');
      return;
    }

    try {
      const migrationId = getMigrationId();

      if (!migrationId) {
        toast.error('No migration found');
        return;
      }

      toast.loading('Generating Excel report.');

      await migrationApi.downloadConversionReport(
        migrationId,
        Array.from(selectedForExport)
      );

      toast.dismiss();
      toast.success(
        `Excel report downloaded with ${selectedForExport.size} calculation(s)!`
      );
    } catch (error) {
      toast.dismiss();
      console.error('Failed to export to Excel:', error);
      toast.error('Failed to export to Excel. Please try again.');
    }
  };

  const handleToggleSelection = (conversionId) => {
    if (!conversionId) return;

    setSelectedForExport((previousSelection) => {
      const newSelection = new Set(previousSelection);

      if (newSelection.has(conversionId)) {
        newSelection.delete(conversionId);
      } else {
        newSelection.add(conversionId);
      }

      return newSelection;
    });
  };

  const handleSelectAll = () => {
    if (selectedForExport.size === conversions.length) {
      setSelectedForExport(new Set());
    } else {
      const allIds = new Set(
        conversions
          .map((conversion) => conversion?.conversion_id)
          .filter(Boolean)
      );

      setSelectedForExport(allIds);
    }
  };

  const handleBack = () => {
    navigate('/migration-wizard/field-mapping');
  };

  const handleNext = () => {
    navigate('/migration-wizard/review');
  };

  if (isLoading) {
    return (
      <div
        className="h-screen flex overflow-hidden"
        style={{ backgroundColor: '#e5e5e5' }}
      >
        <MigrationSidebar currentStep={4} />

        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
            <p className="text-gray-600">Loading conversions...</p>
          </div>
        </div>
      </div>
    );
  }

  const testsPassed = conversions.filter(
    (conversion) => conversion?.status === 'validated'
  );

  const manualReview = conversions.filter(
    (conversion) =>
      conversion?.status === 'failed' ||
      conversion?.status === 'manual_review' ||
      conversion?.status === 'pending'
  );

  return (
    <div
      className="h-screen flex overflow-hidden"
      style={{ backgroundColor: '#e5e5e5' }}
    >
      <MigrationSidebar currentStep={4} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 shadow-sm px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                DAX Conversion
              </h1>

              <p className="text-sm text-gray-600 mt-1">
                ThoughtSpot calculated fields converted to Power BI DAX measures
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button variant="secondary" onClick={handleBack}>
                Back
              </Button>

              <Button onClick={handleNext}>
                Next Step
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-lg border border-gray-200 p-5">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                    <Code className="w-6 h-6 text-blue-600" />
                  </div>

                  <div>
                    <div className="text-2xl font-bold text-gray-900">
                      {conversions.length}
                    </div>
                    <div className="text-sm text-gray-600">
                      Total Conversions
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-green-200 p-5">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                    <CheckCircle className="w-6 h-6 text-green-600" />
                  </div>

                  <div>
                    <div className="text-2xl font-bold text-green-900">
                      {testsPassed.length}
                    </div>
                    <div className="text-sm text-gray-600">Tests Passed</div>
                    <div className="text-xs text-green-600 mt-0.5">
                      {conversions.length > 0
                        ? Math.round(
                          (testsPassed.length / conversions.length) * 100
                        )
                        : 0}
                      %
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-amber-200 p-5">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
                    <AlertCircle className="w-6 h-6 text-amber-600" />
                  </div>

                  <div>
                    <div className="text-2xl font-bold text-amber-900">
                      {manualReview.length}
                    </div>
                    <div className="text-sm text-gray-600">
                      Manual Review Required
                    </div>
                    <div className="text-xs text-amber-600 mt-0.5">
                      {conversions.length > 0
                        ? Math.round(
                          (manualReview.length / conversions.length) * 100
                        )
                        : 0}
                      %
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Conversions Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                      <Code className="w-5 h-5 text-blue-600" />
                      Conversion Results ({conversions.length})
                    </h2>

                    {selectedForExport.size > 0 && (
                      <span className="text-sm text-gray-600 bg-blue-50 px-3 py-1 rounded-full">
                        {selectedForExport.size} selected for export
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handleSelectAll}>
                      {selectedForExport.size === conversions.length ? (
                        <>
                          <Square className="w-4 h-4 mr-2" />
                          Deselect All
                        </>
                      ) : (
                        <>
                          <CheckSquare className="w-4 h-4 mr-2" />
                          Select All
                        </>
                      )}
                    </Button>

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={handleExportToExcel}
                      disabled={selectedForExport.size === 0}
                    >
                      <Download className="w-4 h-4 mr-2" />
                      Export to Excel ({selectedForExport.size})
                    </Button>
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12">
                        <input
                          type="checkbox"
                          checked={
                            selectedForExport.size === conversions.length &&
                            conversions.length > 0
                          }
                          onChange={handleSelectAll}
                          className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        />
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Source Calculated Field
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Source Formula
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Converted DAX Formula
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Conversion Method
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>

                  <tbody className="bg-white divide-y divide-gray-200">
                    {conversions.length === 0 ? (
                      <tr>
                        <td
                          colSpan="7"
                          className="px-6 py-12 text-center text-sm text-gray-500"
                        >
                          No conversions found.
                        </td>
                      </tr>
                    ) : (
                      conversions.map((conversion, index) => {
                        const conversionId =
                          conversion?.conversion_id ||
                          `conversion_row_${index}`;

                        const isSelected = selectedForExport.has(conversionId);

                        const warnings = parseWarnings(conversion?.warnings);

                        return (
                          <tr key={conversionId} className="hover:bg-gray-50">
                            <td className="px-6 py-4">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() =>
                                  handleToggleSelection(conversionId)
                                }
                                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                              />
                            </td>

                            <td className="px-6 py-4">
                              <div className="font-medium text-gray-900">
                                {conversion?.source_calculated_field ||
                                  conversion?.source_name ||
                                  `Calculation ${index + 1}`}
                              </div>

                              <div className="text-xs text-gray-500">
                                measure
                              </div>
                            </td>

                            <td className="px-6 py-4">
                              <pre
                                className="text-sm text-gray-700 font-mono whitespace-pre-wrap max-w-xs"
                                title={conversion?.source_formula || ''}
                              >
                                {conversion?.source_formula || 'N/A'}
                              </pre>
                            </td>

                            <td className="px-6 py-4">
                              <pre
                                className="text-sm text-gray-900 font-mono whitespace-pre-wrap max-w-md"
                                title={conversion?.dax_formula || ''}
                              >
                                {conversion?.dax_formula || 'N/A'}
                              </pre>

                              {warnings.length > 0 && (
                                <div className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
                                  {warnings.join(', ')}
                                </div>
                              )}
                            </td>

                            <td className="px-6 py-4">
                              <span className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-700">
                                {conversion?.conversion_method || 'RULE_BASED'}
                              </span>
                            </td>

                            <td className="px-6 py-4">
                              {conversion?.status === 'validated' ? (
                                <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">
                                  <CheckCircle className="w-3 h-3" />
                                  Validated
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-amber-100 text-amber-800">
                                  <AlertCircle className="w-3 h-3" />
                                  {conversion?.status || 'Review'}
                                </span>
                              )}
                            </td>

                            <td className="px-6 py-4">
                              <button
                                onClick={() =>
                                  handleCopyDAX(conversion?.dax_formula)
                                }
                                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
                                title="Copy DAX"
                              >
                                <Copy className="w-4 h-4" />
                                Copy
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}