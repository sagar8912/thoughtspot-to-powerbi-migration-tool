import React from 'react';
import { AlertCircle, CheckCircle, AlertTriangle, TrendingUp } from 'lucide-react';

const DiscrepancyInspector = ({ validationResults }) => {
  if (!validationResults || !validationResults.test_slices) {
    return null;
  }

  const { test_slices, pass_rate, overall_passed, correction_attempts } = validationResults;

  // Categorize slices
  const passedSlices = test_slices.filter(s => s.passed);
  const failedSlices = test_slices.filter(s => !s.passed);

  // Error category distribution
  const errorCategories = failedSlices.reduce((acc, slice) => {
    const category = slice.error_category;
    acc[category] = (acc[category] || 0) + 1;
    return acc;
  }, {});

  const getErrorIcon = (category) => {
    switch (category) {
      case 'PERFECT_MATCH':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'ROUNDING_ERROR':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'SCALE_ERROR':
        return <AlertTriangle className="w-4 h-4 text-orange-500" />;
      case 'CONTEXT_SHIFT':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
    }
  };

  const getErrorColor = (category) => {
    switch (category) {
      case 'PERFECT_MATCH':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'ROUNDING_ERROR':
        return 'bg-green-50 text-green-700 border-green-200';
      case 'SCALE_ERROR':
        return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'CONTEXT_SHIFT':
        return 'bg-red-100 text-red-800 border-red-300';
      default:
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    }
  };

  return (
    <div className="space-y-4">
      {/* Summary Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Validation Results</h3>
          {overall_passed ? (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
              <CheckCircle className="w-4 h-4 mr-1" />
              100% Match
            </span>
          ) : (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800">
              <AlertTriangle className="w-4 h-4 mr-1" />
              {(pass_rate * 100).toFixed(1)}% Pass Rate
            </span>
          )}
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-sm text-gray-600">Test Slices</div>
            <div className="text-2xl font-bold text-gray-900">{test_slices.length}</div>
          </div>
          <div className="bg-green-50 rounded-lg p-3">
            <div className="text-sm text-green-600">Passed</div>
            <div className="text-2xl font-bold text-green-700">{passedSlices.length}</div>
          </div>
          <div className="bg-red-50 rounded-lg p-3">
            <div className="text-sm text-red-600">Failed</div>
            <div className="text-2xl font-bold text-red-700">{failedSlices.length}</div>
          </div>
          <div className="bg-blue-50 rounded-lg p-3">
            <div className="text-sm text-blue-600">Corrections</div>
            <div className="text-2xl font-bold text-blue-700">{correction_attempts}</div>
          </div>
        </div>

        {/* Error Category Distribution */}
        {failedSlices.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Error Categories</h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(errorCategories).map(([category, count]) => (
                <span
                  key={category}
                  className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border ${getErrorColor(category)}`}
                >
                  {getErrorIcon(category)}
                  <span className="ml-1">{category.replace(/_/g, ' ')}: {count}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Detailed Comparison Table */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h4 className="text-sm font-semibold text-gray-900">Slice-by-Slice Comparison</h4>
          <p className="text-xs text-gray-600 mt-1">Comparing Tableau ground truth vs. DAX execution</p>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Dimensions
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tableau (Truth)
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  DAX (Candidate)
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Delta
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Error Type
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {test_slices.map((slice, index) => (
                <tr key={index} className={slice.passed ? 'bg-white' : 'bg-red-50'}>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {slice.passed ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-500" />
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(slice.dimensions).map(([key, value]) => (
                        <span
                          key={key}
                          className="inline-block px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
                        >
                          {key}: <span className="font-medium">{value}</span>
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-mono text-gray-900">
                    {slice.tableau_value?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || 'NULL'}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-mono">
                    <span className={slice.passed ? 'text-green-700' : 'text-red-700'}>
                      {slice.dax_value?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || 'NULL'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-right">
                    {slice.passed ? (
                      <span className="text-green-600 font-medium">✓ 0.00</span>
                    ) : (
                      <div className="text-right">
                        <div className="text-red-700 font-medium">
                          {slice.delta?.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                        </div>
                        <div className="text-xs text-red-600">
                          ({(slice.relative_error * 100).toFixed(2)}%)
                        </div>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getErrorColor(slice.error_category)}`}
                    >
                      {getErrorIcon(slice.error_category)}
                      <span className="ml-1">{slice.error_category.replace(/_/g, ' ')}</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pass Rate Visualization */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Pass Rate</span>
          <span className="text-2xl font-bold text-gray-900">{(pass_rate * 100).toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-500 ${
              pass_rate === 1 ? 'bg-green-500' : pass_rate > 0.9 ? 'bg-yellow-500' : 'bg-red-500'
            }`}
            style={{ width: `${pass_rate * 100}%` }}
          />
        </div>
        <div className="mt-2 text-xs text-gray-600">
          {pass_rate === 1
            ? '✅ Perfect match - Production ready'
            : pass_rate > 0.9
            ? '⚠️ High accuracy - Minor issues detected'
            : '❌ Requires correction - Review failures'}
        </div>
      </div>
    </div>
  );
};

export default DiscrepancyInspector;
