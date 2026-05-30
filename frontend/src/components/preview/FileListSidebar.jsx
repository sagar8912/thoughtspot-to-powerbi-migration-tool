import { FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react';

const FileListSidebar = ({ files, selectedIndex, onSelectFile }) => {
  return (
    <div className="w-56 bg-gradient-to-b from-slate-50 via-white to-slate-100 border-r border-gray-200 h-screen sticky top-0 flex flex-col">
      {/* Compact Header */}
      <div className="p-3 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-900">Files</h2>
        <p className="text-xs text-gray-500 mt-0.5">{files.length} uploaded</p>
      </div>

      {/* Compact File List */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-2 space-y-1">
          {files.map((file, index) => {
            const isActive = index === selectedIndex;
            const hasDuplicates = file.duplicate_groups && file.duplicate_groups.length > 0;
            const statusColor = hasDuplicates ? 'text-amber-500' : 'text-emerald-500';
            const StatusIcon = hasDuplicates ? AlertCircle : CheckCircle2;

            return (
              <button
                key={file.file_id}
                onClick={() => onSelectFile(index)}
                className={`
                  w-full text-left p-2 rounded-md transition-all duration-150
                  ${isActive
                    ? 'bg-primary-100 border border-primary-300 shadow-sm'
                    : 'bg-white border border-transparent hover:bg-gray-50 hover:border-gray-200'
                  }
                `}
              >
                <div className="flex items-start gap-2">
                  {/* Compact Icon */}
                  <div className={`
                    mt-0.5 p-1.5 rounded
                    ${isActive ? 'bg-primary-200' : 'bg-gray-100'}
                  `}>
                    <FileSpreadsheet className={`w-3.5 h-3.5 ${isActive ? 'text-primary-700' : 'text-gray-600'}`} />
                  </div>

                  {/* Compact Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-1">
                      <h3 className={`
                        text-xs font-medium truncate
                        ${isActive ? 'text-primary-900' : 'text-gray-900'}
                      `}>
                        {file.original_filename}
                      </h3>
                      <StatusIcon className={`w-3 h-3 flex-shrink-0 ${statusColor}`} />
                    </div>

                    {/* Compact Stats */}
                    <div className="mt-1 flex items-center gap-2 text-[10px] text-gray-500">
                      <span>{(file.row_count || 0).toLocaleString()}</span>
                      <span>×</span>
                      <span>{file.column_count}</span>
                    </div>

                    {/* Compact Duplicate Badge */}
                    {hasDuplicates && (
                      <div className="mt-1">
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                          {file.duplicate_groups.length} dup
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Compact Footer */}
      <div className="p-2 border-t border-gray-200 bg-white">
        <div className="text-[10px] text-gray-600 space-y-0.5">
          <div className="flex justify-between">
            <span>Rows</span>
            <span className="font-medium text-gray-900">
              {files.reduce((sum, f) => sum + (f.row_count || 0), 0).toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Cols</span>
            <span className="font-medium text-gray-900">
              {files.reduce((sum, f) => sum + (f.column_count || 0), 0)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileListSidebar;
