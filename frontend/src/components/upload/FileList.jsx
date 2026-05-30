import PropTypes from 'prop-types';
import { config } from '../../config.js';

const FileList = ({ files, onRemove, disabled = false }) => {
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return `${Math.round((bytes / Math.pow(k, i)) * 100) / 100} ${sizes[i]}`;
  };

  const getFileExtension = (fileName) => {
    return `.${fileName.split('.').pop().toLowerCase()}`;
  };

  const isValidFile = (file) => {
    const ext = getFileExtension(file.name);
    const isValidExt = config.allowedExtensions.includes(ext);
    const isValidSize = file.size <= config.maxFileSize;

    return {
      isValidExt,
      isValidSize,
      isValid: isValidExt && isValidSize,
    };
  };

  const getTotalSize = () => {
    return files.reduce((acc, file) => acc + file.size, 0);
  };

  const getAllowedExtensionsLabel = () => {
    return config.allowedExtensions.join(', ');
  };

  if (files.length === 0) {
    return null;
  }

  return (
    <div className="mt-6 bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center">
            <span className="text-white text-sm font-bold">
              {files.length}
            </span>
          </div>
          Selected ThoughtSpot Files
        </h3>

        <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg">
          <svg
            className="w-4 h-4 text-gray-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
            />
          </svg>

          <p className="text-sm font-medium text-gray-700">
            {formatFileSize(getTotalSize())}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        {files.map((file, index) => {
          const validation = isValidFile(file);

          return (
            <div
              key={`${file.name}-${index}`}
              className={`flex items-center justify-between p-3 rounded-xl border transition-all duration-200 ${validation.isValid
                  ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200 hover:shadow-md'
                  : 'bg-gradient-to-r from-red-50 to-orange-50 border-red-200'
                }`}
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <div
                  className={`flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center shadow-sm ${validation.isValid
                      ? 'bg-gradient-to-br from-green-500 to-emerald-600'
                      : 'bg-gradient-to-br from-red-500 to-red-600'
                    }`}
                >
                  {validation.isValid ? (
                    <svg
                      className="w-6 h-6 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  ) : (
                    <svg
                      className="w-6 h-6 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">
                    {file.name}
                  </p>

                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-xs text-gray-600 font-medium">
                      {formatFileSize(file.size)}
                    </p>

                    {!validation.isValid && (
                      <span className="text-xs text-red-700 font-semibold">
                        {!validation.isValidExt && '• Unsupported file type'}
                        {!validation.isValidSize && '• File too large'}
                      </span>
                    )}
                  </div>

                  {!validation.isValidExt && (
                    <p className="text-xs text-red-600 mt-1">
                      Allowed: {getAllowedExtensionsLabel()}
                    </p>
                  )}
                </div>
              </div>

              <button
                onClick={() => onRemove(file.name)}
                disabled={disabled}
                className="flex-shrink-0 ml-3 p-2 text-gray-400 hover:text-red-600 hover:bg-red-100 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                title="Remove file"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          );
        })}
      </div>

      {files.length > config.maxFiles && (
        <div className="mt-4 p-3 bg-gradient-to-r from-red-50 to-orange-50 border border-red-200 rounded-xl">
          <div className="flex items-start gap-2">
            <svg
              className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>

            <p className="text-sm text-red-700 font-medium">
              Maximum {config.maxFiles} files allowed. Please remove{' '}
              {files.length - config.maxFiles} file(s).
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

FileList.propTypes = {
  files: PropTypes.arrayOf(PropTypes.object).isRequired,
  onRemove: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

export default FileList;