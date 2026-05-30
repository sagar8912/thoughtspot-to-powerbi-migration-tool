import PropTypes from 'prop-types';

const FileNode = ({ data }) => {
  return (
    <div className="file-node bg-gradient-to-br from-white to-gray-50 rounded-xl shadow-lg border-2 border-gray-200 p-4 min-w-[280px] hover:shadow-xl transition-all duration-300">
      <div className="mb-3 pb-3 border-b-2 border-gradient-to-r from-primary-200 to-blue-200">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center shadow-md">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-bold text-gray-900 truncate" title={data.label}>
              {data.label}
            </h3>
            {data.sheet && (
              <p className="text-xs text-gray-600 font-medium mt-0.5">{data.sheet}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs mt-3">
          <div className="flex items-center gap-1.5 px-2 py-1 bg-blue-50 rounded-lg border border-blue-200">
            <svg className="w-3.5 h-3.5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7h16M4 12h16M4 17h16" />
            </svg>
            <span className="font-semibold text-blue-700">{data.rowCount?.toLocaleString()} rows</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-1 bg-purple-50 rounded-lg border border-purple-200">
            <svg className="w-3.5 h-3.5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
            </svg>
            <span className="font-semibold text-purple-700">{data.columnCount} cols</span>
          </div>
        </div>
      </div>
      {/* Column nodes will be rendered as children below this */}
    </div>
  );
};

FileNode.propTypes = {
  data: PropTypes.shape({
    label: PropTypes.string.isRequired,
    sheet: PropTypes.string,
    rowCount: PropTypes.number,
    columnCount: PropTypes.number,
    columns: PropTypes.array
  }).isRequired
};

export default FileNode;
