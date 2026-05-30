import { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  useReactTable,
  getCoreRowModel,
  flexRender
} from '@tanstack/react-table';
import EnhancedColumnHeader from './EnhancedColumnHeader';
import usePreviewStore from '../../stores/previewStore';

const DataSpreadsheetView = ({ fileId, columns }) => {
  const { isColumnMarkedForDeletion } = usePreviewStore();

  // Generate sample rows from column data
  const rows = useMemo(() => {
    if (!columns || columns.length === 0) return [];

    // Get max length of sample values
    const maxSamples = Math.max(...columns.map(col => col.sample_values?.length || 0));

    // Create rows
    const generatedRows = [];
    for (let i = 0; i < Math.min(maxSamples, 20); i++) {
      const row = { _rowIndex: i + 1 };
      columns.forEach(col => {
        row[col.name] = col.sample_values?.[i] ?? '';
      });
      generatedRows.push(row);
    }

    return generatedRows;
  }, [columns]);

  // Define table columns with enhanced headers
  const tableColumns = useMemo(
    () => [
      {
        id: '_rowIndex',
        header: '#',
        accessorKey: '_rowIndex',
        size: 50,
        cell: ({ getValue }) => (
          <div className="text-xs font-mono text-gray-400 text-center">
            {getValue()}
          </div>
        )
      },
      ...columns.map(col => ({
        id: col.name,
        accessorKey: col.name,
        header: () => (
          <EnhancedColumnHeader column={col} fileId={fileId} />
        ),
        size: 150,
        cell: ({ getValue }) => {
          const value = getValue();
          const isMarked = isColumnMarkedForDeletion(fileId, col.name);

          return (
            <div
              className={`
                text-xs font-mono truncate
                ${isMarked ? 'text-red-400 line-through opacity-50' : 'text-gray-900'}
              `}
              title={String(value)}
            >
              {String(value)}
            </div>
          );
        }
      }))
    ],
    [columns, fileId, isColumnMarkedForDeletion]
  );

  const table = useReactTable({
    data: rows,
    columns: tableColumns,
    getCoreRowModel: getCoreRowModel()
  });

  return (
    <div className="max-h-[600px] overflow-auto border border-gray-300 rounded-lg bg-white shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gradient-to-b from-slate-50 to-slate-100 sticky top-0 z-10">
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th
                  key={header.id}
                  className="px-3 py-3 text-center border-r border-gray-200 last:border-r-0"
                  style={{ width: header.getSize() }}
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="bg-white divide-y divide-gray-100">
          {table.getRowModel().rows.map((row, idx) => (
            <tr
              key={row.id}
              className={`hover:bg-blue-50 transition-colors ${
                idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'
              }`}
            >
              {row.getVisibleCells().map(cell => (
                <td
                  key={cell.id}
                  className="px-3 py-2 border-r border-gray-200 last:border-r-0"
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {rows.length === 0 && (
        <div className="text-center py-8 text-gray-500 text-xs">
          No sample data available
        </div>
      )}
    </div>
  );
};

DataSpreadsheetView.propTypes = {
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

export default DataSpreadsheetView;
