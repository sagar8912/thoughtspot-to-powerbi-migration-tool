/**
 * Calculations List - Display all conversions in a table
 */
import { CheckCircle, AlertCircle, Clock, ExternalLink } from 'lucide-react';

export default function CalculationsList({ conversions, onSelect }) {
  if (!conversions || conversions.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <p className="text-lg font-medium mb-2">No conversions yet</p>
        <p className="text-sm">Conversions will appear here once processing begins.</p>
      </div>
    );
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'validated':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-600" />;
      case 'manual_review':
        return <AlertCircle className="w-5 h-5 text-yellow-600" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getValidationStatusBadge = (conversion) => {
    // Show validation status instead of confidence percentage
    const status = conversion.status;

    // Check if validation was actually run (test_slices > 0 would be ideal, but we use status)
    if (status === 'validated') {
      return (
        <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">
          ✓ Test Passed
        </span>
      );
    } else if (status === 'manual_review') {
      return (
        <span className="px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
          ⚠ Manual Review
        </span>
      );
    } else if (status === 'failed') {
      return (
        <span className="px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800">
          ✗ Failed
        </span>
      );
    } else {
      // pending or unknown status
      return (
        <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800">
          ⏳ Pending
        </span>
      );
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Calculation
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              DAX Formula
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Method
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Validation Status
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {conversions.map((conversion, index) => (
            <tr
              key={conversion.conversion_id}
              className="hover:bg-gray-50 transition-colors"
            >
              <td className="px-4 py-4">
                <div className="flex items-center">
                  {getStatusIcon(conversion.status)}
                </div>
              </td>

              <td className="px-4 py-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {conversion.calc_name || `Calculation ${index + 1}`}
                  </p>
                  <p className="text-xs text-gray-500 mt-1 truncate max-w-xs">
                    {conversion.tableau_formula || 'N/A'}
                  </p>
                </div>
              </td>

              <td className="px-4 py-4">
                <code className="text-xs bg-gray-100 px-2 py-1 rounded max-w-md block truncate">
                  {conversion.dax_formula}
                </code>
              </td>

              <td className="px-4 py-4">
                <span className="text-xs text-gray-600">
                  {conversion.conversion_method}
                </span>
              </td>

              <td className="px-4 py-4">
                {getValidationStatusBadge(conversion)}
              </td>

              <td className="px-4 py-4">
                <button
                  onClick={() => onSelect(conversion.conversion_id)}
                  className="text-blue-600 hover:text-blue-700 text-sm font-medium flex items-center gap-1"
                >
                  View
                  <ExternalLink className="w-3 h-3" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
