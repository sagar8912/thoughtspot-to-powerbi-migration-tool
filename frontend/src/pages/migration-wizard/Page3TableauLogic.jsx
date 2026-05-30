/**
 * Page 3: Field Mapping - Tableau Logic Extraction
 * Shows Calculated Fields, Parameters, Measures, and LOD Expressions
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calculator, Sliders, BarChart2, AlertTriangle, Loader } from 'lucide-react';
import toast from 'react-hot-toast';

import Button from '../../components/common/Button';
import MigrationSidebar from '../../components/migration/MigrationSidebar';
import useMigrationStore from '../../stores/migrationStore';
import useMigrationCacheStore from '../../stores/migrationCacheStore';

export default function Page3TableauLogic() {
  const navigate = useNavigate();
  const { currentMigration } = useMigrationStore();
  const loadWorkbookMetadata = useMigrationCacheStore(
    (state) => state.loadWorkbookMetadata
  );

  const [isLoading, setIsLoading] = useState(true);
  const [metadata, setMetadata] = useState(null);

  useEffect(() => {
    if (!currentMigration?.migration_id) {
      toast.error('No migration found. Please upload a TWBX file first.');
      navigate('/migration');
      return;
    }
    loadMetadata();
  }, [currentMigration, navigate]);

  // OPTIMIZATION: Use cached metadata from Page 1
  // OLD: fetch('/workbook-metadata') - 15-30 seconds (DUPLICATE CALL!)
  // NEW: loadWorkbookMetadata() - instant if cached from Page 1
  const loadMetadata = async () => {
    setIsLoading(true);
    try {
      console.log('[Page3] Loading workbook metadata (cached or fresh)...');
      const data = await loadWorkbookMetadata(currentMigration.migration_id);
      setMetadata(data);
      console.log('[Page3] Metadata loaded - using cache if available');
    } catch (error) {
      console.error('Failed to load metadata:', error);
      toast.error('Failed to load Tableau metadata');
    } finally {
      setIsLoading(false);
    }
  };

  // Extract calculated fields
  const getCalculatedFields = () => {
    if (!metadata?.workbooks) return [];

    // Build map for formula replacement (internal name -> readable name)
    const calcMap = {};
    metadata.workbooks.forEach(wb => {
      wb.calculated_fields.forEach(cf => {
        const displayName = cf.caption || cf.name;
        calcMap[cf.name] = displayName;
      });
    });

    const replaceInternalNames = (formula) => {
      if (!formula) return "";
      let updatedFormula = formula;

      // Replace all internal names with readable names
      Object.keys(calcMap).forEach(internalName => {
        const readableName = calcMap[internalName];
        // Escape check: assuming internalName doesn't contain regex special chars except potentially what we control
        const regex = new RegExp(`\\[${internalName}\\]`, "g");
        updatedFormula = updatedFormula.replace(regex, `[${readableName}]`);
      });

      return updatedFormula;
    };

    return metadata.workbooks.flatMap(wb =>
      wb.calculated_fields.map(cf => ({
        ...cf,
        name: cf.caption || cf.name, // Use caption if available
        formula: replaceInternalNames(cf.formula), // Clean formula
        workbook: wb.filename
      }))
    );
  };

  // Extract parameters
  const getParameters = () => {
    if (!metadata?.workbooks) return [];
    return metadata.workbooks.flatMap(wb =>
      (wb.parameters || []).map(p => ({
        ...p,
        workbook: wb.filename
      }))
    );
  };

  // Extract measures from data sources
  const getMeasures = () => {
    if (!metadata?.workbooks) return [];
    const measures = [];
    metadata.workbooks.forEach(wb => {
      wb.data_sources?.forEach(ds => {
        ds.table_details?.forEach(table => {
          table.column_details?.forEach(col => {
            if (col.role === 'measure') {
              measures.push({
                name: col.name,
                table: table.table_name,
                datatype: col.datatype,
                aggregation: col.aggregation || 'SUM',
                workbook: wb.filename
              });
            }
          });
        });
      });
    });
    return measures;
  };

  // Extract LOD expressions from calculated fields
  const getLODExpressions = () => {
    const calcFields = getCalculatedFields();
    return calcFields.filter(cf =>
      cf.formula && /\{(FIXED|INCLUDE|EXCLUDE)/.test(cf.formula)
    );
  };

  if (isLoading) {
    return (
      <div className="h-screen flex overflow-hidden" style={{ backgroundColor: '#e5e5e5' }}>
        <MigrationSidebar currentStep={3} />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
            <p className="text-gray-600">Loading Tableau metadata...</p>
          </div>
        </div>
      </div>
    );
  }

  const calculatedFields = getCalculatedFields();
  const parameters = getParameters();
  const measures = getMeasures();
  const lodExpressions = getLODExpressions();

  return (
    <div className="h-screen flex overflow-hidden" style={{ backgroundColor: '#e5e5e5' }}>
      <MigrationSidebar currentStep={3} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 shadow-sm px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Field Mapping</h1>
              <p className="text-sm text-gray-600 mt-1">
                Review Tableau calculated fields, parameters, and measures
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                onClick={() => {
                  const lastJobId = localStorage.getItem('last_job_id');
                  if (lastJobId) {
                    navigate(`/jobs/${lastJobId}/results`);
                  } else {
                    navigate('/migration-wizard/model-intelligence');
                  }
                }}
              >
                Back
              </Button>
              <Button onClick={() => navigate('/migration-wizard/formula-conversion')}>
                Next Step
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Calculator className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-gray-900">{calculatedFields.length}</div>
                    <div className="text-xs text-gray-600">Calculated Fields</div>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                    <Sliders className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-gray-900">{parameters.length}</div>
                    <div className="text-xs text-gray-600">Parameters</div>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                    <BarChart2 className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-gray-900">{measures.length}</div>
                    <div className="text-xs text-gray-600">Measures</div>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                    <AlertTriangle className="w-5 h-5 text-red-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-gray-900">{lodExpressions.length}</div>
                    <div className="text-xs text-gray-600">LOD Expressions</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Calculated Fields Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Calculator className="w-5 h-5 text-blue-600" />
                  Calculated Fields ({calculatedFields.length})
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Calculated Field
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Formula
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Class
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {calculatedFields.map((field, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {field.name}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-700 font-mono max-w-md truncate">
                          {field.formula || 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${field.role === 'measure'
                            ? 'bg-green-100 text-green-800'
                            : 'bg-blue-100 text-blue-800'
                            }`}>
                            {field.role}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Parameters Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Sliders className="w-5 h-5 text-purple-600" />
                  Parameters (Filters) ({parameters.length})
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Columns
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Worksheet
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Type
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Members
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {parameters.length === 0 ? (
                      <tr>
                        <td colSpan="4" className="px-6 py-8 text-center text-sm text-gray-500">
                          No parameters found in this workbook
                        </td>
                      </tr>
                    ) : (
                      parameters.map((param, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {param.name || param.column || 'N/A'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                            {param.worksheet || 'All'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                            {param.datatype || param.type || 'String'}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-700">
                            {param.allowable_values?.join(', ') || param.value || 'N/A'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Measures Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <BarChart2 className="w-5 h-5 text-green-600" />
                  Measures ({measures.length})
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Column
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Aggregation
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {measures.map((measure, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {measure.name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                          {measure.table}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                          <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                            {measure.aggregation}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* LOD Expressions */}
            {lodExpressions.length > 0 && (
              <div className="bg-white rounded-lg border-2 border-red-200 overflow-hidden">
                <div className="px-6 py-4 bg-red-50 border-b border-red-200">
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-600" />
                    Level of Detail (LOD) Expressions ({lodExpressions.length})
                    <span className="px-2 py-1 bg-red-200 text-red-800 rounded text-xs font-medium">
                      CRITICAL
                    </span>
                  </h2>
                  <p className="text-sm text-red-800 mt-2">
                    LOD expressions require careful manual review during DAX conversion
                  </p>
                </div>
                <div className="p-6 space-y-4">
                  {lodExpressions.map((lod, idx) => (
                    <div key={idx} className="border-2 border-red-100 rounded-lg p-4 bg-red-50">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900 mb-2">{lod.name}</h3>
                          <div className="bg-white rounded p-3 font-mono text-sm text-gray-800 border border-red-200">
                            {lod.formula}
                          </div>
                        </div>
                      </div>
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
