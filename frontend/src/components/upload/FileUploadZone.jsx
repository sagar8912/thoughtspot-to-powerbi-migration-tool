import { useState } from 'react';
import PropTypes from 'prop-types';
import { config } from '../../config.js';

const FileUploadZone = ({
  onFilesSelected,
  disabled = false,
  accept,
  maxFiles,
  title = 'Upload ThoughtSpot files',
  description = 'Drag and drop or browse to choose ThoughtSpot metadata files'
}) => {
  const [isDragging, setIsDragging] = useState(false);

  // Use custom values or fallback to config
  const acceptedExtensions = accept
    ? accept.split(',').map((item) => item.trim()).filter(Boolean)
    : config.allowedExtensions;

  const maxFilesCount = maxFiles || config.maxFiles;
  const maxFileSize = config.maxFileSize;

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (!disabled) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();

    setIsDragging(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();

    setIsDragging(false);

    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    onFilesSelected(files);
  };

  const handleFileInput = (e) => {
    if (disabled) return;

    const files = Array.from(e.target.files);
    onFilesSelected(files);

    // Reset input so same file can be selected again
    e.target.value = '';
  };

  const acceptedFileText = acceptedExtensions.join(', ');
  const acceptedFileInput = accept || config.allowedExtensions.join(',');

  return (
    <div
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`
        relative border-2 border-dashed rounded-xl p-12 text-center transition-all duration-300
        ${isDragging
          ? 'border-primary-500 bg-gradient-to-br from-primary-50 to-blue-50 scale-[1.02]'
          : 'border-gray-300 bg-gradient-to-br from-white to-gray-50'
        }
        ${!disabled
          ? 'cursor-pointer hover:border-primary-400 hover:shadow-lg hover:scale-[1.01]'
          : 'opacity-50 cursor-not-allowed'
        }
      `}
    >
      <input
        type="file"
        multiple
        accept={acceptedFileInput}
        onChange={handleFileInput}
        disabled={disabled}
        className="hidden"
        id="file-upload"
      />

      <label
        htmlFor="file-upload"
        className={`${!disabled ? 'cursor-pointer' : 'cursor-not-allowed'}`}
      >
        <div className="flex flex-col items-center gap-4">
          {/* Cloud Upload Icon with Animation */}
          <div className={`relative transition-all duration-300 ${isDragging ? 'scale-110' : ''}`}>
            <div
              className={`absolute inset-0 bg-primary-400 rounded-full blur-xl opacity-30 ${isDragging ? 'animate-pulse' : ''
                }`}
            ></div>

            <div
              className={`relative w-20 h-20 rounded-2xl flex items-center justify-center ${isDragging
                  ? 'bg-gradient-to-br from-primary-500 to-primary-600'
                  : 'bg-gradient-to-br from-gray-100 to-gray-200'
                }`}
            >
              <svg
                className={`w-10 h-10 transition-colors duration-300 ${isDragging ? 'text-white' : 'text-gray-500'
                  }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            </div>
          </div>

          <div>
            <p className="text-xl font-semibold text-gray-800 mb-1">
              {isDragging ? 'Drop your ThoughtSpot files here' : title}
            </p>

            <p className="text-sm text-gray-500">
              {description.includes('browse') ? description.split('browse')[0] : 'Drag and drop or '}
              <span className="text-primary-600 font-semibold hover:text-primary-700 transition-colors">
                browse
              </span>
              {description.includes('browse')
                ? description.split('browse')[1] || ' to choose files'
                : ' to choose files'}
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 mt-2">
            <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg border border-gray-200 shadow-sm">
              <svg
                className="w-4 h-4 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>

              <span className="text-xs font-medium text-gray-700">
                {acceptedFileText}
              </span>
            </div>

            <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg border border-gray-200 shadow-sm">
              <svg
                className="w-4 h-4 text-blue-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
              </svg>

              <span className="text-xs font-medium text-gray-700">
                Max {maxFilesCount} files
              </span>
            </div>

            <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg border border-gray-200 shadow-sm">
              <svg
                className="w-4 h-4 text-purple-600"
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

              <span className="text-xs font-medium text-gray-700">
                {maxFileSize / (1024 * 1024)}MB each
              </span>
            </div>
          </div>
        </div>
      </label>
    </div>
  );
};

FileUploadZone.propTypes = {
  onFilesSelected: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  accept: PropTypes.string,
  maxFiles: PropTypes.number,
  title: PropTypes.string,
  description: PropTypes.string
};

export default FileUploadZone;