/**
 * Validation Summary - Display validation results
 */
import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';

import migrationApi from '../../services/migrationApi';
import Card from '../common/Card';

export default function ValidationSummary({ migrationId }) {
  const [validationData, setValidationData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadValidationResults();
  }, [migrationId]);

  const loadValidationResults = async () => {
    setIsLoading(true);

    try {
      const data = await migrationApi.getValidationResults(migrationId);
      setValidationData(data);
    } catch (error) {
      console.error('Failed to load validation results:', error);
      toast.error('Failed to load validation results');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">Loading validation results...</p>
      </div>
    );
  }

  if (!validationData || !validationData.results || validationData.results.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <AlertTriangle className="w-12 h-12 text-yellow-600 mx-auto mb-4" />
        <p className="text-lg font-medium mb-2">No validation results yet</p>
        <p className="text-sm">
          Validation will run automatically after conversions are complete.
        </p>
      </div>
    );
  }

  const summary = validationData.summary;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <p className="text-sm text-gray-600 mb-1">Total Conversions</p>
          <p className="text-2xl font-bold text-gray-900">
            {summary.total_conversions}
          </p>
        </Card>

        <Card className="p-4 bg-green-50 border-green-200">
          <p className="text-sm text-green-700 mb-1">Passed</p>
          <p className="text-2xl font-bold text-green-900">
            {summary.passed}
          </p>
        </Card>

        <Card className="p-4 bg-red-50 border-red-200">
          <p className="text-sm text-red-700 mb-1">Failed</p>
          <p className="text-2xl font-bold text-red-900">
            {summary.failed}
          </p>
        </Card>

        <Card className="p-4 bg-blue-50 border-blue-200">
          <p className="text-sm text-blue-700 mb-1">Pass Rate</p>
          <p className="text-2xl font-bold text-blue-900">
            {summary.pass_rate.toFixed(1)}%
          </p>
        </Card>
      </div>

      {/* Detailed Results */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Validation Details
        </h3>

        <div className="space-y-4">
          {validationData.results.map((result, index) => (
            <div
              key={index}
              className={`p-4 rounded-lg border-2 ${
                result.overall_passed
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  {result.overall_passed ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-600" />
                  )}
                  <span className="font-medium text-gray-900">
                    Conversion {index + 1}
                  </span>
                </div>

                {result.correction_attempts > 0 && (
                  <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                    {result.correction_attempts} correction
                    {result.correction_attempts > 1 ? 's' : ''}
                  </span>
                )}
              </div>

              {/* Test Slices */}
              {result.test_slices && result.test_slices.length > 0 && (
                <div className="mt-3 space-y-2">
                  {result.test_slices.map((slice, sliceIndex) => (
                    <div
                      key={sliceIndex}
                      className="text-sm bg-white rounded p-3 border border-gray-200"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-gray-700">
                          Test Slice {sliceIndex + 1}
                        </span>
                        <span
                          className={`text-xs font-medium ${
                            slice.passed ? 'text-green-600' : 'text-red-600'
                          }`}
                        >
                          {slice.passed ? '✓ PASS' : '✗ FAIL'}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div>
                          <span className="text-gray-500">Dimensions:</span>
                          <span className="ml-2 text-gray-900">
                            {JSON.stringify(slice.dimensions)}
                          </span>
                        </div>

                        <div>
                          <span className="text-gray-500">Error Category:</span>
                          <span className="ml-2 text-gray-900">
                            {slice.error_category}
                          </span>
                        </div>

                        <div>
                          <span className="text-gray-500">Tableau Value:</span>
                          <span className="ml-2 text-gray-900">
                            {slice.tableau_value?.toFixed(2) || 'N/A'}
                          </span>
                        </div>

                        <div>
                          <span className="text-gray-500">DAX Value:</span>
                          <span className="ml-2 text-gray-900">
                            {slice.dax_value?.toFixed(2) || 'N/A'}
                          </span>
                        </div>

                        {!slice.passed && (
                          <>
                            <div>
                              <span className="text-gray-500">Delta:</span>
                              <span className="ml-2 text-red-600 font-medium">
                                {slice.delta?.toFixed(4)}
                              </span>
                            </div>

                            <div>
                              <span className="text-gray-500">Relative Error:</span>
                              <span className="ml-2 text-red-600 font-medium">
                                {(slice.relative_error * 100).toFixed(2)}%
                              </span>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
