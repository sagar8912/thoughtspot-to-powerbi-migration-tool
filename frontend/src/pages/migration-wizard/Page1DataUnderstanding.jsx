/**
 * Page 1: Data Understanding - COMMAND CENTER DASHBOARD
 *
 * Design:
 * - Left sidebar with all steps
 * - Lucide React icons only (no emojis)
 * - Background: #e5e5e5
 * - Compact table display (no column details section)
 */
/**
 * Page 1: Data Understanding - Source Dashboard Exploration
 *
 * ThoughtSpot to Power BI migration wizard
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Grid,
  Layout,
  Code,
  Database,
  Search,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import toast from 'react-hot-toast';

import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import useMigrationStore from '../../stores/migrationStore';
import useMigrationCacheStore from '../../stores/migrationCacheStore';
import MigrationSidebar from '../../components/migration/MigrationSidebar';

export default function Page1DataUnderstanding() {
  const navigate = useNavigate();

  const { currentMigration } = useMigrationStore();

  const loadWorkbookMetadata = useMigrationCacheStore(
    (state) => state.loadWorkbookMetadata
  );

  const [isLoading, setIsLoading] = useState(true);
  const [metadata, setMetadata] = useState(null);

  const [worksheetSearch, setWorksheetSearch] = useState('');
  const [calcFieldSearch, setCalcFieldSearch] = useState('');
  const [tableSearch, setTableSearch] = useState('');

  const [expandedFormulas, setExpandedFormulas] = useState(new Set());
  const [selectedWorksheet, setSelectedWorksheet] = useState(null);

  const loadComprehensiveMetadata = useCallback(
    async (migrationId) => {
      setIsLoading(true);

      try {
        console.log('[Page1] Loading source metadata...');
        const data = await loadWorkbookMetadata(migrationId);
        setMetadata(data);
        console.log('[Page1] Source metadata loaded');
      } catch (error) {
        console.error('Failed to load metadata:', error);
        toast.error(
          'Failed to load migration data. The source file may still be processing.'
        );
      } finally {
        setIsLoading(false);
      }
    },
    [loadWorkbookMetadata]
  );

  useEffect(() => {
    if (!currentMigration?.migration_id) {
      toast.error('No migration found. Please upload a ThoughtSpot file first.');
      navigate('/migration');
      return;
    }

    loadComprehensiveMetadata(currentMigration.migration_id);
  }, [currentMigration?.migration_id, navigate, loadComprehensiveMetadata]);

  const handleNext = () => {
    navigate('/migration-wizard/model-intelligence');
  };

  const toggleFormula = (fieldName) => {
    setExpandedFormulas((previous) => {
      const updated = new Set(previous);

      if (updated.has(fieldName)) {
        updated.delete(fieldName);
      } else {
        updated.add(fieldName);
      }

      return updated;
    });
  };

  const escapeRegex = (value) => {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  };

  const buildCalculationMap = () => {
    const map = {};

    if (!Array.isArray(metadata?.workbooks)) {
      return map;
    }

    metadata.workbooks.forEach((workbook) => {
      if (!Array.isArray(workbook?.calculated_fields)) {
        return;
      }

      workbook.calculated_fields.forEach((field) => {
        const internalName = field?.name;
        const displayName = field?.caption || field?.name;

        if (internalName && displayName) {
          map[internalName] = displayName;
        }
      });
    });

    return map;
  };

  const replaceInternalNames = (formula, calcMap) => {
    if (!formula) return '';

    let updatedFormula = formula;

    Object.keys(calcMap)
      .sort((a, b) => b.length - a.length)
      .forEach((internalName) => {
        const readableName = calcMap[internalName];
        const escapedName = escapeRegex(internalName);

        const bracketRegex = new RegExp(`\\[${escapedName}\\]`, 'g');
        updatedFormula = updatedFormula.replace(
          bracketRegex,
          `[${readableName}]`
        );

        const wordRegex = new RegExp(`\\b${escapedName}\\b`, 'g');
        updatedFormula = updatedFormula.replace(wordRegex, readableName);
      });

    return updatedFormula;
  };

  const getFriendlyName = (name) => {
    if (!name) return name;

    const calcMap = buildCalculationMap();

    if (calcMap[name]) {
      return calcMap[name];
    }

    return replaceInternalNames(name, calcMap);
  };

  const getAllWorksheets = () => {
    if (!Array.isArray(metadata?.workbooks)) return [];

    const worksheets = metadata.workbooks.flatMap((workbook) =>
      Array.isArray(workbook?.worksheets)
        ? workbook.worksheets.map((worksheet) => ({
          ...worksheet,
          workbook: workbook?.filename || 'Unknown',
        }))
        : []
    );

    if (!worksheetSearch) return worksheets;

    const search = worksheetSearch.toLowerCase();

    return worksheets.filter((worksheet) =>
      worksheet?.name?.toLowerCase().includes(search)
    );
  };

  const getAllCalculatedFields = () => {
    if (!Array.isArray(metadata?.workbooks)) return [];

    const calcMap = buildCalculationMap();

    const fields = metadata.workbooks.flatMap((workbook) =>
      Array.isArray(workbook?.calculated_fields)
        ? workbook.calculated_fields.map((field) => ({
          id: field?.id,
          name: field?.caption || field?.name || 'Unnamed Field',
          formula: replaceInternalNames(field?.formula, calcMap),
          workbook: workbook?.filename || 'Unknown',
          role: field?.role || 'measure',
          datatype: field?.datatype || 'unknown',
        }))
        : []
    );

    let filtered = fields;

    if (calcFieldSearch) {
      const search = calcFieldSearch.toLowerCase();

      filtered = filtered.filter(
        (field) =>
          field?.name?.toLowerCase().includes(search) ||
          field?.formula?.toLowerCase().includes(search)
      );
    }

    if (selectedWorksheet) {
      const worksheetCalcNames = new Set();

      if (Array.isArray(selectedWorksheet?.measures)) {
        selectedWorksheet.measures.forEach((measure) => {
          if (measure?.type === 'calculated') {
            worksheetCalcNames.add(getFriendlyName(measure?.name));
            worksheetCalcNames.add(measure?.name);
          }
        });
      }

      const allCalcNames = new Set(fields.map((field) => field.name));

      if (Array.isArray(selectedWorksheet?.dimensions)) {
        selectedWorksheet.dimensions.forEach((dimension) => {
          const friendlyDimension = getFriendlyName(dimension);

          if (allCalcNames.has(dimension)) {
            worksheetCalcNames.add(dimension);
          }

          if (allCalcNames.has(friendlyDimension)) {
            worksheetCalcNames.add(friendlyDimension);
          }
        });
      }

      filtered = filtered.filter((field) => worksheetCalcNames.has(field.name));
    }

    return filtered;
  };

  const getAllTables = () => {
    if (!Array.isArray(metadata?.workbooks)) return [];

    const allTables = metadata.workbooks.flatMap((workbook) =>
      Array.isArray(workbook?.data_sources)
        ? workbook.data_sources.flatMap((dataSource) =>
          Array.isArray(dataSource?.table_details)
            ? dataSource.table_details.map((table) => ({
              ...table,
              data_source: dataSource?.name || 'Unknown',
              workbook: workbook?.filename || 'Unknown',
            }))
            : []
        )
        : []
    );

    const uniqueTables = [];
    const seenTableNames = new Set();

    allTables.forEach((table) => {
      const tableName = table?.display_name || table?.table_name;

      if (tableName && !seenTableNames.has(tableName)) {
        seenTableNames.add(tableName);
        uniqueTables.push(table);
      }
    });

    if (!tableSearch) return uniqueTables;

    const search = tableSearch.toLowerCase();

    return uniqueTables.filter((table) =>
      (table?.display_name || table?.table_name || '')
        .toLowerCase()
        .includes(search)
    );
  };

  const summary = metadata?.summary || {};

  return (
    <div
      className="h-screen flex overflow-hidden"
      style={{ backgroundColor: '#e5e5e5' }}
    >
      <MigrationSidebar currentStep={1} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 shadow-sm px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Source Dashboard Exploration
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                Complete inspection of your ThoughtSpot source assets
              </p>
            </div>

            <Button onClick={handleNext} size="md" className="px-6">
              Next Step
            </Button>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex-1 flex items-center justify-center">
            <Card className="p-8">
              <div className="flex items-center gap-3 mb-4">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
                <span className="text-lg text-gray-700">
                  Loading source metadata...
                </span>
              </div>

              <p className="text-sm text-gray-500 text-center">
                Extracting dashboards, worksheets, calculated fields, tables,
                and metadata...
              </p>
            </Card>
          </div>
        )}

        {/* Dashboard Content */}
        {!isLoading && metadata && (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Summary Bar */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
              <div className="grid grid-cols-4 gap-6">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                    <Layout className="w-6 h-6 text-purple-600" />
                  </div>

                  <div>
                    <div className="text-2xl font-bold text-gray-900">
                      {summary.total_dashboards || 0}
                    </div>
                    <div className="text-xs text-gray-600 font-medium">
                      Dashboards
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Grid className="w-6 h-6 text-blue-600" />
                  </div>

                  <div>
                    <div className="text-2xl font-bold text-gray-900">
                      {summary.total_worksheets || 0}
                    </div>
                    <div className="text-xs text-gray-600 font-medium">
                      Worksheets
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                    <Database className="w-6 h-6 text-orange-600" />
                  </div>

                  <div>
                    <div className="text-2xl font-bold text-gray-900">
                      {summary.total_tables || 0}
                    </div>
                    <div className="text-xs text-gray-600 font-medium">
                      Data Tables
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                    <Code className="w-6 h-6 text-green-600" />
                  </div>

                  <div>
                    <div className="text-2xl font-bold text-gray-900">
                      {summary.total_calculated_fields || 0}
                    </div>
                    <div className="text-xs text-gray-600 font-medium">
                      Calculated Fields
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Main Grid */}
            <div className="flex-1 overflow-auto p-6">
              <div className="grid grid-cols-2 gap-6 mb-6">
                {/* Worksheets Card */}
                <Card className="flex flex-col" style={{ height: '450px' }}>
                  <div className="p-4 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-3">
                      <Grid className="w-5 h-5 text-blue-600" />
                      Worksheets / Charts ({getAllWorksheets().length})
                    </h2>

                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search worksheets..."
                        value={worksheetSearch}
                        onChange={(event) =>
                          setWorksheetSearch(event.target.value)
                        }
                        className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto p-4">
                    <div className="space-y-2">
                      {getAllWorksheets().map((worksheet, index) => (
                        <div
                          key={`${worksheet?.name || 'worksheet'}-${index}`}
                          className={`p-3 rounded-lg transition-colors cursor-pointer border ${selectedWorksheet?.name === worksheet?.name
                              ? 'bg-blue-50 border-blue-300 ring-1 ring-blue-300'
                              : 'bg-gray-50 border-transparent hover:bg-gray-100'
                            }`}
                          onClick={() =>
                            setSelectedWorksheet(
                              selectedWorksheet?.name === worksheet?.name
                                ? null
                                : worksheet
                            )
                          }
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <h3 className="font-semibold text-gray-900 text-sm">
                                {worksheet?.name || 'Unnamed Worksheet'}
                              </h3>

                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-xs text-gray-500">
                                  Chart Type:{' '}
                                  {worksheet?.chart_type ||
                                    worksheet?.visual_type ||
                                    'Unknown'}
                                </span>
                              </div>
                            </div>

                            {selectedWorksheet?.name === worksheet?.name ? (
                              <ChevronUp className="w-4 h-4 text-blue-500" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-gray-400" />
                            )}
                          </div>

                          {selectedWorksheet?.name === worksheet?.name && (
                            <div className="mt-3 pt-3 border-t border-blue-200 text-xs space-y-2">
                              <div className="grid grid-cols-2 gap-2 mb-2">
                                <div>
                                  <span className="font-semibold text-gray-700 block mb-1">
                                    Dimensions:
                                  </span>

                                  <div className="max-h-24 overflow-y-auto bg-white border border-blue-100 rounded p-1 space-y-0.5">
                                    {Array.isArray(worksheet?.dimensions) &&
                                      worksheet.dimensions.length > 0 ? (
                                      worksheet.dimensions.map(
                                        (dimension, dimensionIndex) => (
                                          <div
                                            key={dimensionIndex}
                                            className="truncate text-gray-600 pl-1 border-l-2 border-purple-200"
                                          >
                                            {getFriendlyName(dimension)}
                                          </div>
                                        )
                                      )
                                    ) : (
                                      <span className="text-gray-400 italic pl-1">
                                        None
                                      </span>
                                    )}
                                  </div>
                                </div>

                                <div>
                                  <span className="font-semibold text-gray-700 block mb-1">
                                    Base Measures:
                                  </span>

                                  <div className="max-h-24 overflow-y-auto bg-white border border-blue-100 rounded p-1 space-y-0.5">
                                    {Array.isArray(worksheet?.measures) &&
                                      worksheet.measures.filter(
                                        (measure) =>
                                          measure?.type === 'base_measure'
                                      ).length > 0 ? (
                                      worksheet.measures
                                        .filter(
                                          (measure) =>
                                            measure?.type === 'base_measure'
                                        )
                                        .map((measure, measureIndex) => (
                                          <div
                                            key={measureIndex}
                                            className="truncate pl-1 border-l-2 border-gray-300 text-gray-600"
                                          >
                                            {getFriendlyName(measure?.name)}
                                          </div>
                                        ))
                                    ) : (
                                      <span className="text-gray-400 italic pl-1">
                                        None
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>

                              {(worksheet?.axes?.rows ||
                                worksheet?.axes?.columns ||
                                worksheet?.chart_type === 'Card') && (
                                  <div className="mt-2 pt-2 border-t border-gray-100">
                                    <span className="text-xs font-semibold uppercase text-gray-500 block mb-1.5">
                                      Axes
                                    </span>

                                    <div className="grid grid-cols-2 gap-2">
                                      <div>
                                        <span className="text-[10px] uppercase text-gray-400 font-semibold tracking-wide">
                                          Rows
                                        </span>

                                        <div
                                          className="text-gray-600 truncate bg-white px-1.5 py-0.5 rounded border border-blue-100 mt-0.5"
                                          title={
                                            worksheet?.axes?.rows
                                              ? getFriendlyName(
                                                worksheet.axes.rows
                                              )
                                              : ''
                                          }
                                        >
                                          {worksheet?.axes?.rows
                                            ? getFriendlyName(
                                              worksheet.axes.rows
                                            )
                                            : worksheet?.chart_type === 'Card' &&
                                              worksheet?.measures?.[0]?.name
                                              ? getFriendlyName(
                                                worksheet.measures[0].name
                                              )
                                              : '-'}
                                        </div>
                                      </div>

                                      <div>
                                        <span className="text-[10px] uppercase text-gray-400 font-semibold tracking-wide">
                                          Columns
                                        </span>

                                        <div
                                          className="text-gray-600 truncate bg-white px-1.5 py-0.5 rounded border border-blue-100 mt-0.5"
                                          title={
                                            worksheet?.axes?.columns
                                              ? getFriendlyName(
                                                worksheet.axes.columns
                                              )
                                              : ''
                                          }
                                        >
                                          {worksheet?.axes?.columns
                                            ? getFriendlyName(
                                              worksheet.axes.columns
                                            )
                                            : worksheet?.chart_type === 'Card' &&
                                              worksheet?.dimensions?.[0]
                                              ? getFriendlyName(
                                                worksheet.dimensions[0]
                                              )
                                              : '-'}
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </Card>

                {/* Calculated Fields Card */}
                <Card className="flex flex-col" style={{ height: '450px' }}>
                  <div className="p-4 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-3">
                      <Code className="w-5 h-5 text-green-600" />
                      Calculated Fields ({getAllCalculatedFields().length})
                    </h2>

                    {selectedWorksheet && (
                      <div className="flex items-center gap-2 mb-2 p-2 bg-blue-50 rounded border border-blue-100 text-xs">
                        <span className="font-medium text-blue-800">
                          Filtered by: {selectedWorksheet.name}
                        </span>

                        <button
                          type="button"
                          onClick={() => setSelectedWorksheet(null)}
                          className="ml-auto text-blue-600 hover:text-blue-800 font-semibold"
                        >
                          Clear
                        </button>
                      </div>
                    )}

                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search fields or formulas..."
                        value={calcFieldSearch}
                        onChange={(event) =>
                          setCalcFieldSearch(event.target.value)
                        }
                        className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto p-4">
                    <div className="space-y-2">
                      {getAllCalculatedFields().map((field, index) => (
                        <div
                          key={`${field?.name || 'field'}-${index}`}
                          className="border border-gray-200 rounded-lg overflow-hidden hover:border-gray-300 transition-colors"
                        >
                          <div
                            className="p-3 bg-white cursor-pointer flex items-center justify-between"
                            onClick={() => toggleFormula(field.name)}
                          >
                            <div className="flex-1">
                              <h3 className="font-semibold text-gray-900 text-sm">
                                {field.name}
                              </h3>

                              <div className="flex items-center gap-2 mt-1">
                                <span
                                  className={`text-xs px-2 py-0.5 rounded-full ${field.role === 'measure'
                                      ? 'bg-green-100 text-green-700'
                                      : 'bg-blue-100 text-blue-700'
                                    }`}
                                >
                                  {field.role}
                                </span>

                                <span className="text-xs text-gray-500">
                                  {field.datatype}
                                </span>
                              </div>
                            </div>

                            {expandedFormulas.has(field.name) ? (
                              <ChevronUp className="w-4 h-4 text-gray-400" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-gray-400" />
                            )}
                          </div>

                          {expandedFormulas.has(field.name) && (
                            <div className="px-3 py-2 bg-gray-50 border-t border-gray-200">
                              <code className="text-xs text-gray-800 font-mono break-all">
                                {field.formula || 'No formula found'}
                              </code>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </Card>
              </div>

              {/* Data Tables Card */}
              <Card className="flex flex-col" style={{ height: '500px' }}>
                <div className="p-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-3">
                    <Database className="w-5 h-5 text-orange-600" />
                    Data Tables ({getAllTables().length})
                  </h2>

                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />

                    <input
                      type="text"
                      placeholder="Search tables..."
                      value={tableSearch}
                      onChange={(event) => setTableSearch(event.target.value)}
                      className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    />
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4">
                  <div className="space-y-4">
                    {getAllTables().map((table, index) => (
                      <div
                        key={`${table?.display_name || table?.table_name || 'table'}-${index}`}
                        className="border border-gray-200 rounded-lg overflow-hidden"
                      >
                        <div className="bg-gradient-to-r from-gray-50 to-gray-100 px-4 py-3 border-b border-gray-200">
                          <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-gray-900">
                              {table?.display_name ||
                                table?.table_name ||
                                'Unnamed Table'}
                            </h3>

                            <span className="text-sm text-gray-600">
                              {(table?.row_count || 0).toLocaleString()} rows ×{' '}
                              {table?.column_details?.length || 0} columns
                            </span>
                          </div>
                        </div>

                        <div className="overflow-x-auto">
                          <table className="min-w-full divide-y divide-gray-200 text-sm">
                            <thead className="bg-gray-100">
                              <tr>
                                {(table?.column_details || []).map(
                                  (column, columnIndex) => (
                                    <th
                                      key={columnIndex}
                                      className="px-3 py-2 text-left text-xs font-medium text-gray-600 uppercase tracking-wider whitespace-nowrap"
                                    >
                                      {column?.name}
                                    </th>
                                  )
                                )}
                              </tr>
                            </thead>

                            <tbody className="bg-white divide-y divide-gray-200">
                              {(table?.data_preview || [])
                                .slice(0, 5)
                                .map((row, rowIndex) => (
                                  <tr
                                    key={rowIndex}
                                    className="hover:bg-gray-50"
                                  >
                                    {(table?.column_details || []).map(
                                      (column, cellIndex) => (
                                        <td
                                          key={cellIndex}
                                          className="px-3 py-2 whitespace-nowrap text-xs text-gray-900"
                                        >
                                          {row?.[column?.name] !== null &&
                                            row?.[column?.name] !== undefined ? (
                                            String(row[column.name])
                                          ) : (
                                            <span className="text-gray-400 italic">
                                              null
                                            </span>
                                          )}
                                        </td>
                                      )
                                    )}
                                  </tr>
                                ))}
                            </tbody>
                          </table>

                          <div className="px-4 py-2 bg-gray-50 text-xs text-gray-600 text-center border-t border-gray-200">
                            Showing 5 of{' '}
                            {(table?.row_count || 0).toLocaleString()} rows
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}