import { useState } from 'react';
import PropTypes from 'prop-types';
import { FileText, Hash, Calendar, CheckSquare, Circle } from 'lucide-react';
import { extractOriginalFilename } from '../../utils/fileUtils.js';

const TablePreview = ({ files }) => {
  const [activeFileIndex, setActiveFileIndex] = useState(0);

  if (!files || files.length === 0) {
    return null;
  }

  const currentFile = files[activeFileIndex];
  const rows = currentFile?.preview_data || [];
  const columns = currentFile?.columns || [];

  const getTypeIcon = (dataType) => {
    const iconClass = "w-4 h-4";
    switch (dataType?.toLowerCase()) {
      case 'string':
      case 'text':
        return <FileText className={`${iconClass} text-blue-600`} />;
      case 'number':
      case 'int':
      case 'float':
        return <Hash className={`${iconClass} text-green-600`} />;
      case 'date':
      case 'datetime':
        return <Calendar className={`${iconClass} text-purple-600`} />;
      case 'boolean':
      case 'bool':
        return <CheckSquare className={`${iconClass} text-orange-600`} />;
      default:
        return <Circle className={`${iconClass} text-gray-600`} />;
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 animate-fade-in">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Table Preview
      </h3>

      {/* File tabs */}
      {files.length > 1 && (
        <div className="flex gap-2 mb-4 overflow-x-auto pb-2">
          {files.map((file, index) => (
            <button
              key={index}
              onClick={() => setActiveFileIndex(index)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                activeFileIndex === index
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {extractOriginalFilename(file.file_name)}
            </button>
          ))}
        </div>
      )}

      {/* Table info */}
      <div className="mb-3 text-sm text-gray-600">
        <p className="font-medium">{extractOriginalFilename(currentFile?.file_name)}</p>
        <p className="text-xs mt-1">
          {currentFile?.row_count} rows × {currentFile?.column_count} columns
          {currentFile?.sheet_name && ` • Sheet: ${currentFile.sheet_name}`}
        </p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((col, idx) => {
                // Support both column_name (fixed backend) and name (legacy)
                const columnName = col.column_name || col.name;
                return (
                  <th
                    key={idx}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider"
                  >
                    <div className="flex items-center gap-2">
                      {getTypeIcon(col.data_type)}
                      <span className="truncate max-w-[150px]" title={columnName}>
                        {columnName}
                      </span>
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {rows.slice(0, 20).map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-gray-50">
                {columns.map((col, colIdx) => {
                  // Support both column_name (fixed backend) and name (legacy)
                  const columnName = col.column_name || col.name;
                  return (
                    <td
                      key={colIdx}
                      className="px-4 py-2 text-sm text-gray-900 whitespace-nowrap"
                    >
                      <div className="max-w-[200px] truncate" title={row[columnName]}>
                        {row[columnName] ?? '-'}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > 20 && (
        <p className="text-xs text-gray-500 mt-2 text-center">
          Showing first 20 of {rows.length} rows
        </p>
      )}
    </div>
  );
};

TablePreview.propTypes = {
  files: PropTypes.arrayOf(PropTypes.shape({
    file_name: PropTypes.string,
    sheet_name: PropTypes.string,
    row_count: PropTypes.number,
    column_count: PropTypes.number,
    columns: PropTypes.array,
    preview_data: PropTypes.array
  }))
};

export default TablePreview;
