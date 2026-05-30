import PropTypes from 'prop-types';

const ProgressBar = ({ progress, className = '', showLabel = true, animated = true }) => {
  return (
    <div className={`w-full ${className}`}>
      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full bg-primary-600 rounded-full transition-all duration-300 ${animated ? 'animate-pulse-slow' : ''}`}
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
      {showLabel && (
        <div className="text-xs text-gray-600 mt-1 text-right">
          {Math.round(progress)}%
        </div>
      )}
    </div>
  );
};

ProgressBar.propTypes = {
  progress: PropTypes.number.isRequired,
  className: PropTypes.string,
  showLabel: PropTypes.bool,
  animated: PropTypes.bool
};

export default ProgressBar;
