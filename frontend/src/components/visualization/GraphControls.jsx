import PropTypes from 'prop-types';
import { useReactFlow } from 'reactflow';

/**
 * Graph Controls Toolbar Component
 * Provides zoom, fit view, and layout reset controls for the graph
 */
const GraphControls = ({ onResetLayout }) => {
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  const handleZoomIn = () => {
    zoomIn({ duration: 300 });
  };

  const handleZoomOut = () => {
    zoomOut({ duration: 300 });
  };

  const handleFitView = () => {
    fitView({ duration: 300, padding: 0.2 });
  };

  const handleResetLayout = () => {
    if (onResetLayout) {
      onResetLayout();
    }
    // Also fit view after reset
    setTimeout(() => {
      fitView({ duration: 300, padding: 0.2 });
    }, 100);
  };

  return (
    <div className="absolute top-4 right-4 z-10 flex flex-col gap-2 bg-white rounded-xl shadow-lg p-2 border-2 border-gray-200">
      {/* Zoom In */}
      <button
        onClick={handleZoomIn}
        className="p-2.5 rounded-lg hover:bg-gradient-to-br hover:from-primary-50 hover:to-blue-50 transition-all duration-200 group border border-transparent hover:border-primary-200"
        title="Zoom In"
        aria-label="Zoom in"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5 text-gray-600 group-hover:text-primary-600 transition-colors"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Zoom Out */}
      <button
        onClick={handleZoomOut}
        className="p-2.5 rounded-lg hover:bg-gradient-to-br hover:from-primary-50 hover:to-blue-50 transition-all duration-200 group border border-transparent hover:border-primary-200"
        title="Zoom Out"
        aria-label="Zoom out"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5 text-gray-600 group-hover:text-primary-600 transition-colors"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent my-1" />

      {/* Fit View */}
      <button
        onClick={handleFitView}
        className="p-2.5 rounded-lg hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 transition-all duration-200 group border border-transparent hover:border-green-200"
        title="Fit View"
        aria-label="Fit to view"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5 text-gray-600 group-hover:text-green-600 transition-colors"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M3 4a1 1 0 011-1h4a1 1 0 010 2H6.414l2.293 2.293a1 1 0 01-1.414 1.414L5 6.414V8a1 1 0 01-2 0V4zm9 1a1 1 0 010-2h4a1 1 0 011 1v4a1 1 0 01-2 0V6.414l-2.293 2.293a1 1 0 11-1.414-1.414L13.586 5H12zm-9 7a1 1 0 012 0v1.586l2.293-2.293a1 1 0 011.414 1.414L6.414 15H8a1 1 0 010 2H4a1 1 0 01-1-1v-4zm13-1a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 010-2h1.586l-2.293-2.293a1 1 0 011.414-1.414L15 13.586V12a1 1 0 011-1z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Reset Layout */}
      {onResetLayout && (
        <>
          <div className="h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent my-1" />
          <button
            onClick={handleResetLayout}
            className="p-2.5 rounded-lg hover:bg-gradient-to-br hover:from-orange-50 hover:to-amber-50 transition-all duration-200 group border border-transparent hover:border-orange-200"
            title="Reset Layout"
            aria-label="Reset layout"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5 text-gray-600 group-hover:text-orange-600 transition-colors"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </>
      )}
    </div>
  );
};

GraphControls.propTypes = {
  onResetLayout: PropTypes.func
};

export default GraphControls;
