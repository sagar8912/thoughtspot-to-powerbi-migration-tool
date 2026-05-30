import PropTypes from 'prop-types';
import ProgressBar from '../common/ProgressBar.jsx';

const UploadProgress = ({ progress, fileName }) => {
  return (
    <div className="mt-6 bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-shrink-0">
          <svg
            className="w-8 h-8 text-primary-600 animate-pulse"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
            />
          </svg>
        </div>

        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900">
            Uploading ThoughtSpot Files...
          </h3>

          {fileName && (
            <p className="text-sm text-gray-500 mt-1">
              {fileName}
            </p>
          )}
        </div>
      </div>

      <ProgressBar progress={progress} animated={true} />

      <p className="text-xs text-gray-500 mt-4 text-center">
        Please wait while we upload your ThoughtSpot metadata files to the server
      </p>
    </div>
  );
};

UploadProgress.propTypes = {
  progress: PropTypes.number.isRequired,
  fileName: PropTypes.string,
};

export default UploadProgress;