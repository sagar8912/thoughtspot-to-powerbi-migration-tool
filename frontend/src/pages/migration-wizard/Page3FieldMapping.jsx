/**
 * Page 3: Calculated Fields Mapping
 * Shows ThoughtSpot calculated fields and suggested Power BI mappings.
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Layout,
  Loader,
  Search,
  ArrowRight,
  CheckCircle,
  Database,
  Code,
} from 'lucide-react';
import toast from 'react-hot-toast';

import Button from '../../components/common/Button';
import MigrationSidebar from '../../components/migration/MigrationSidebar';
import useMigrationStore from '../../stores/migrationStore';
import migrationApi from '../../services/migrationApi';
import useMigrationCacheStore from '../../stores/migrationCacheStore';

export default function Page3FieldMapping() {
  const navigate = useNavigate();
  const { currentMigration } = useMigrationStore();

  const loadWorkbookMetadata = useMigrationCacheStore(
    (state) => state.loadWorkbookMetadata
  );

  const [isLoading, setIsLoading] = useState(true);
  const [calculatedFields, setCalculatedFields] = useState([]);
  const [tables, setTables] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

  const getMigrationId = useCallback(() => {
    return (
      currentMigration?.migration_id ||
      currentMigration?.job_id ||
      localStorage.getItem('last_job_id')
    );
  }, [currentMigration]);

  const normalizeCalculatedField = (field, index) => {
    const name =
      field?.name ||
      field?.calc_name ||
      field?.caption ||
      field?.display_name ||
      `Calculated Field ${index + 1}`;

    const formula =
      field?.formula ||
      field?.calc_formula ||
      field?.expr ||
      field?.source_formula ||
      '';

    const dataType =
      field?.datatype ||
      field?.data_type ||
      field?.type ||
      'double';

    const role =
      field?.role ||
      field?.calc_type ||
      'measure';

    return {
      id: field?.id || field?.calc_id || `field_${index + 1}`,
      sourceName: name,
      targetName: name,
      sourceFormula: formula,
      targetType: role === 'dimension' ? 'Column' : 'Measure',
      dataType,
      role,
      status: 'Mapped',
    };
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
      const [metadata, resultData] = await Promise.all([
        loadWorkbookMetadata(migrationId).catch(() => null),
        migrationApi.getMigrationResult(migrationId).catch(() => null),
      ]);

      const result = resultData?.result || resultData || {};

      let fields =
        metadata?.calculations ||
        metadata?.formulas ||
        result?.calculations ||
        result?.formulas ||
        [];

      if ((!fields || fields.length === 0) && Array.isArray(metadata?.workbooks)) {
        fields = metadata.workbooks.flatMap(
          (workbook) => workbook?.calculated_fields || []
        );
      }

      if ((!fields || fields.length === 0) && Array.isArray(result?.workbooks)) {
        fields = result.workbooks.flatMap(
          (workbook) => workbook?.calculated_fields || []
        );
      }

      let tableList =
        metadata?.tables ||
        result?.tables ||
        [];

      if ((!tableList || tableList.length === 0) && Array.isArray(metadata?.workbooks)) {
        tableList = metadata.workbooks.flatMap((workbook) =>
          (workbook?.data_sources || []).flatMap(
            (source) => source?.table_details || []
          )
        );
      }

      if ((!tableList || tableList.length === 0) && Array.isArray(result?.workbooks)) {
        tableList = result.workbooks.flatMap((workbook) =>
          (workbook?.data_sources || []).flatMap(
            (source) => source?.table_details || []
          )
        );
      }

      setCalculatedFields(
        Array.isArray(fields)
          ? fields.map((field, index) => normalizeCalculatedField(field, index))
          : []
      );

      setTables(Array.isArray(tableList) ? tableList : []);
    } catch (error) {
      console.error('Failed to load field mapping data:', error);
      toast.error('Failed to load field mapping data');
    } finally {
      setIsLoading(false);
    }
  }, [getMigrationId, loadWorkbookMetadata, navigate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const filteredFields = calculatedFields.filter((field) => {
    const keyword = searchTerm.toLowerCase();

    return (
      field.sourceName.toLowerCase().includes(keyword) ||
      field.targetName.toLowerCase().includes(keyword) ||
      field.sourceFormula.toLowerCase().includes(keyword)
    );
  });

  if (isLoading) {
    return (
      <div
        className="h-screen flex overflow-hidden"
        style={{ backgroundColor: '#e5e5e5' }}
      >
        <MigrationSidebar currentStep={3} />

        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
            <p className="text-gray-600">Loading field mappings...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="h-screen flex overflow-hidden"
      style={{ backgroundColor: '#e5e5e5' }}
    >
      <MigrationSidebar currentStep={3} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 shadow-sm px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Calculated Fields Mapping
              </h1>

              <p className="text-sm text-gray-600 mt-1">
                Map ThoughtSpot calculated fields and source columns to Power BI
                measures and columns.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                onClick={() => navigate('/migration-wizard/model-intelligence')}
              >
                Back
              </Button>

              <Button
                onClick={() => navigate('/migration-wizard/formula-conversion')}
              >
                Next Step
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white rounded-lg border border-gray-200 p-5">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                    <Layout className="w-6 h-6 text-purple-600" />
                  </div>

                  <div>
                    <p className="text-2xl font-bold text-gray-900">
                      {calculatedFields.length}
                    </p>
                    <p className="text-sm text-gray-600">
                      Calculated Fields
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-5">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center">
                    <Database className="w-6 h-6 text-orange-600" />
                  </div>

                  <div>
                    <p className="text-2xl font-bold text-gray-900">
                      {tables.length}
                    </p>
                    <p className="text-sm text-gray-600">
                      Source Tables
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-5">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                    <CheckCircle className="w-6 h-6 text-green-600" />
                  </div>

                  <div>
                    <p className="text-2xl font-bold text-gray-900">
                      {calculatedFields.length}
                    </p>
                    <p className="text-sm text-gray-600">
                      Auto Mapped
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Search */}
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="relative">
                <Search className="w-5 h-5 text-gray-400 absolute left-3 top-3" />

                <input
                  type="text"
                  placeholder="Search calculated fields or formulas..."
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Mapping Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Code className="w-5 h-5 text-blue-600" />
                  Field Mapping Results ({filteredFields.length})
                </h2>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        ThoughtSpot Field
                      </th>

                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Mapping
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Power BI Field
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Source Formula
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Type
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                    </tr>
                  </thead>

                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredFields.length === 0 ? (
                      <tr>
                        <td
                          colSpan="6"
                          className="px-6 py-10 text-center text-sm text-gray-500"
                        >
                          No calculated fields found.
                        </td>
                      </tr>
                    ) : (
                      filteredFields.map((field) => (
                        <tr key={field.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4">
                            <div className="font-medium text-gray-900">
                              {field.sourceName}
                            </div>

                            <div className="text-xs text-gray-500">
                              ThoughtSpot {field.role}
                            </div>
                          </td>

                          <td className="px-6 py-4 text-center">
                            <ArrowRight className="w-5 h-5 text-blue-600 mx-auto" />
                          </td>

                          <td className="px-6 py-4">
                            <div className="font-medium text-gray-900">
                              {field.targetName}
                            </div>

                            <div className="text-xs text-gray-500">
                              Power BI {field.targetType}
                            </div>
                          </td>

                          <td
                            className="px-6 py-4 text-sm text-gray-700 font-mono max-w-xs truncate"
                            title={field.sourceFormula || 'N/A'}
                          >
                            {field.sourceFormula || 'N/A'}
                          </td>

                          <td className="px-6 py-4">
                            <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800">
                              {field.dataType}
                            </span>
                          </td>

                          <td className="px-6 py-4">
                            <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">
                              <CheckCircle className="w-3 h-3" />
                              {field.status}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Source Tables */}
            {tables.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <Database className="w-5 h-5 text-orange-600" />
                    Source Tables ({tables.length})
                  </h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-6">
                  {tables.map((table, index) => (
                    <div
                      key={`${table.table_name || table.name || index}`}
                      className="border border-gray-200 rounded-lg p-4"
                    >
                      <h3 className="font-semibold text-gray-900">
                        {table.table_name ||
                          table.display_name ||
                          table.name ||
                          `Table ${index + 1}`}
                      </h3>

                      <p className="text-sm text-gray-600 mt-1">
                        Rows: {table.row_count ?? 0}
                      </p>

                      <p className="text-sm text-gray-600">
                        Columns:{' '}
                        {(table.column_details || table.columns || []).length}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}