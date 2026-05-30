import { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender
} from '@tanstack/react-table';
import { Hash, FileText, Calendar, CheckSquare, AlertCircle, Trash2 } from 'lucide-react';
import usePreviewStore from '../../stores/previewStore';

const ColumnPreviewTable = ({ fileId, columns }) => {
  const { isColumnMarkedForDeletion, toggleColumnDeletion } = usePreviewStore();

  // Define table columns
  const tableColumns = useMemo(
    () => [
      {
        accessorKey: 'action',
        header: 'Action',
        size: 80,
        cell: ({ row }) => {
          const columnName = row.original.name;
          const isMarked = isColumnMarkedForDeletion(fileId, columnName);

          return (
            <button
              onClick={() => toggleColumnDeletion(fileId, columnName)}
              className={`p-2 rounded-lg transition-all duration-200 ${
                isMarked
                  ? 'bg-red-100 text-red-700 hover:bg-red-200'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              title={isMarked ? 'Keep this column' : 'Delete this column'}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          );
        }
      },
      {
        accessorKey: 'name',
        header: 'Column Name',
        size: 200,
        cell: ({ getValue, row }) => {
          const isMarked = isColumnMarkedForDeletion(fileId, row.original.name);
          return (
            <div
              className={`font-medium transition-all ${
                isMarked ? 'text-red-600 line-through' : 'text-gray-900'
              }`}
            >
              {getValue()}
            </div>
          );
        }
      },
      {
        accessorKey: 'data_type',
        header: 'Type',
        size: 100,
        cell: ({ getValue }) => {
          const type = getValue()?.toLowerCase();
          const iconClass = "w-4 h-4 inline mr-2";

          let icon;
          let colorClass;

          switch (type) {
            case 'string':
            case 'text':
              icon = <FileText className={`${iconClass} text-blue-600`} />;
              colorClass = 'text-blue-700 bg-blue-50';
              break;
            case 'int':
            case 'float':
            case 'number':
              icon = <Hash className={`${iconClass} text-green-600`} />;
              colorClass = 'text-green-700 bg-green-50';
              break;
            case 'datetime':
            case 'date':
              icon = <Calendar className={`${iconClass} text-purple-600`} />;
              colorClass = 'text-purple-700 bg-purple-50';
              break;
            case 'boolean':
            case 'bool':
              icon = <CheckSquare className={`${iconClass} text-orange-600`} />;
              colorClass = 'text-orange-700 bg-orange-50';
              break;
            default:
              icon = <AlertCircle className={`${iconClass} text-gray-600`} />;
              colorClass = 'text-gray-700 bg-gray-50';
          }

          return (
            <span className={`px-2 py-1 rounded-md text-xs font-semibold ${colorClass}`}>
              {icon}
              {type}
            </span>
          );
        }
      },
      {
        accessorKey: 'unique_count',
        header: 'Unique',
        size: 120,
        cell: ({ getValue, row }) => {
          const uniqueCount = getValue();
          const totalCount = row.original.null_count + uniqueCount;
          const percentage = totalCount > 0 ? ((uniqueCount / totalCount) * 100).toFixed(1) : 0;

          // Color coding based on uniqueness
          let barColor = 'bg-emerald-500';
          if (percentage < 50) barColor = 'bg-red-500';
          else if (percentage < 80) barColor = 'bg-amber-500';

          return (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-gray-900">{percentage}%</span>
                <span className="text-xs text-gray-500">{uniqueCount.toLocaleString()}</span>
              </div>
              {/* Progress Bar */}
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full ${barColor} transition-all duration-300`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          );
        }
      },
      {
        accessorKey: 'null_count',
        header: 'Nulls',
        size: 120,
        cell: ({ getValue, row }) => {
          const nullCount = getValue();
          const totalCount = row.original.null_count + row.original.unique_count;
          const percentage = totalCount > 0 ? ((nullCount / totalCount) * 100).toFixed(1) : 0;

          // Color coding - green for low nulls, red for high
          let barColor = 'bg-red-500';
          if (percentage < 5) barColor = 'bg-emerald-500';
          else if (percentage < 20) barColor = 'bg-amber-500';

          return (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className={`font-medium ${nullCount > 0 ? 'text-orange-600' : 'text-gray-900'}`}>
                  {percentage}%
                </span>
                <span className="text-xs text-gray-500">{nullCount.toLocaleString()}</span>
              </div>
              {/* Progress Bar */}
              {nullCount > 0 && (
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full ${barColor} transition-all duration-300`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              )}
            </div>
          );
        }
      },
      {
        accessorKey: 'sample_values',
        header: 'Sample Values',
        size: 300,
        cell: ({ getValue }) => {
          const samples = getValue() || [];
          const displaySamples = samples.slice(0, 3);

          return (
            <div className="text-xs text-gray-600 space-y-1">
              {displaySamples.map((value, idx) => (
                <div key={idx} className="truncate max-w-[250px]" title={String(value)}>
                  {String(value)}
                </div>
              ))}
              {samples.length > 3 && (
                <div className="text-gray-400 italic">+{samples.length - 3} more...</div>
              )}
            </div>
          );
        }
      }
    ],
    [fileId, isColumnMarkedForDeletion, toggleColumnDeletion]
  );

  const table = useReactTable({
    data: columns,
    columns: tableColumns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel()
  });

  return (
    <div className="overflow-x-auto border border-gray-200 rounded-lg">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th
                  key={header.id}
                  className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100 transition-colors"
                  style={{ width: header.getSize() }}
                  onClick={header.column.getToggleSortingHandler()}
                >
                  <div className="flex items-center gap-2">
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                    {header.column.getIsSorted() && (
                      <span className="text-primary-600">
                        {header.column.getIsSorted() === 'asc' ? '↑' : '↓'}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {table.getRowModel().rows.map(row => (
            <tr
              key={row.id}
              className={`hover:bg-gray-50 transition-colors ${
                isColumnMarkedForDeletion(fileId, row.original.name)
                  ? 'bg-red-50 opacity-60'
                  : ''
              }`}
            >
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="px-4 py-3 text-sm">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {columns.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No columns found
        </div>
      )}
    </div>
  );
};

ColumnPreviewTable.propTypes = {
  fileId: PropTypes.string.isRequired,
  columns: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      data_type: PropTypes.string.isRequired,
      null_count: PropTypes.number.isRequired,
      unique_count: PropTypes.number.isRequired,
      sample_values: PropTypes.array
    })
  ).isRequired
};

export default ColumnPreviewTable;
