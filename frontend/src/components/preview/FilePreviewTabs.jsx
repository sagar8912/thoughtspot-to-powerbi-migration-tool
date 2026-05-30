import PropTypes from 'prop-types';
import { FileText, AlertTriangle } from 'lucide-react';
import usePreviewStore from '../../stores/previewStore';

const FilePreviewTabs = ({ files }) => {
  const { selectedFileIndex, setSelectedFileIndex } = usePreviewStore();

  if (!files || files.length === 0) return null;

  return (
    <div className="border-b border-gray-200 mb-6">
      <div className="flex gap-2 overflow-x-auto pb-2">
        {files.map((file, index) => {
          const isActive = selectedFileIndex === index;
          const duplicateCount = file.duplicate_groups?.length || 0;

          return (
            <button
              key={file.file_id}
              onClick={() => setSelectedFileIndex(index)}
              className={`flex items-center gap-2 px-4 py-3 rounded-t-lg text-sm font-medium transition-all whitespace-nowrap border-b-2 ${
                isActive
                  ? 'bg-white text-primary-700 border-primary-600'
                  : 'bg-gray-50 text-gray-700 hover:bg-gray-100 border-transparent'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span className="truncate max-w-[200px]" title={file.original_filename}>
                {file.original_filename}
              </span>

              {duplicateCount > 0 && (
                <span className="flex items-center gap-1 px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full text-xs font-semibold">
                  <AlertTriangle className="w-3 h-3" />
                  {duplicateCount}
                </span>
              )}

              <span className="text-xs text-gray-500">
                {file.row_count.toLocaleString()} rows
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

FilePreviewTabs.propTypes = {
  files: PropTypes.arrayOf(
    PropTypes.shape({
      file_id: PropTypes.string.isRequired,
      original_filename: PropTypes.string.isRequired,
      row_count: PropTypes.number.isRequired,
      column_count: PropTypes.number.isRequired,
      duplicate_groups: PropTypes.array
    })
  ).isRequired
};

export default FilePreviewTabs;
