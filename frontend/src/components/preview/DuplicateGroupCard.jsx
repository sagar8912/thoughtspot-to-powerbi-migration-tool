import PropTypes from 'prop-types';
import { AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import usePreviewStore from '../../stores/previewStore';

const DuplicateGroupCard = ({ fileId, group }) => {
  const { isColumnMarkedForDeletion, toggleColumnDeletion } = usePreviewStore();

  const getDetectionTypeBadge = (type) => {
    const badges = {
      exact_name: { text: 'Exact Name Match', color: 'bg-red-100 text-red-800' },
      suffix_pattern: { text: 'Suffix Pattern', color: 'bg-orange-100 text-orange-800' },
      content_similar: { text: 'Content Similar', color: 'bg-yellow-100 text-yellow-800' },
      fuzzy_name: { text: 'Fuzzy Name Match', color: 'bg-blue-100 text-blue-800' },
      llm_semantic: { text: 'LLM Semantic', color: 'bg-purple-100 text-purple-800' }
    };

    const badge = badges[type] || { text: type, color: 'bg-gray-100 text-gray-800' };

    return (
      <span className={`px-3 py-1 rounded-full text-xs font-semibold ${badge.color}`}>
        {badge.text}
      </span>
    );
  };

  const getSimilarityColor = (score) => {
    if (score >= 95) return 'text-red-600';
    if (score >= 85) return 'text-orange-600';
    if (score >= 70) return 'text-yellow-600';
    return 'text-blue-600';
  };

  return (
    <div className="bg-white border-2 border-yellow-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-600" />
          <div>
            <div className="flex items-center gap-2 mb-1">
              {getDetectionTypeBadge(group.detection_type)}
              <span className={`text-sm font-semibold ${getSimilarityColor(group.similarity_score)}`}>
                {group.similarity_score.toFixed(0)}% similar
              </span>
            </div>
            <p className="text-xs text-gray-600 mt-1">
              <span className="font-medium">Recommendation:</span> {group.recommendation}
            </p>
          </div>
        </div>
      </div>

      {/* Column List */}
      <div className="space-y-3">
        {group.columns.map((columnName, index) => {
          const isMarked = isColumnMarkedForDeletion(fileId, columnName);
          const isFirst = index === 0;
          const sampleValues = group.metadata?.sample_comparison?.[columnName] || [];

          return (
            <div
              key={columnName}
              className={`border rounded-lg p-3 transition-all ${
                isMarked
                  ? 'border-red-300 bg-red-50'
                  : isFirst
                  ? 'border-green-300 bg-green-50'
                  : 'border-gray-200 bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {isMarked ? (
                    <XCircle className="w-4 h-4 text-red-600" />
                  ) : isFirst ? (
                    <CheckCircle className="w-4 h-4 text-green-600" />
                  ) : (
                    <CheckCircle className="w-4 h-4 text-gray-400" />
                  )}
                  <span
                    className={`font-medium ${
                      isMarked ? 'text-red-700 line-through' : 'text-gray-900'
                    }`}
                  >
                    {columnName}
                  </span>
                  {isFirst && (
                    <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full font-semibold">
                      Keep
                    </span>
                  )}
                  {isMarked && (
                    <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-semibold">
                      Delete
                    </span>
                  )}
                </div>

                {!isFirst && (
                  <button
                    onClick={() => toggleColumnDeletion(fileId, columnName)}
                    className={`px-3 py-1 rounded-md text-xs font-semibold transition-colors ${
                      isMarked
                        ? 'bg-green-100 text-green-700 hover:bg-green-200'
                        : 'bg-red-100 text-red-700 hover:bg-red-200'
                    }`}
                  >
                    {isMarked ? 'Keep' : 'Delete'}
                  </button>
                )}
              </div>

              {/* Sample Values */}
              {sampleValues.length > 0 && (
                <div className="mt-2 pl-6">
                  <div className="text-xs text-gray-600 space-y-0.5">
                    <div className="font-medium text-gray-700 mb-1">Sample values:</div>
                    {sampleValues.slice(0, 3).map((value, idx) => (
                      <div key={idx} className="truncate" title={String(value)}>
                        {String(value)}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* LLM Reasoning (if available) */}
      {group.metadata?.llm_reasoning && (
        <div className="mt-4 pt-4 border-t border-yellow-200">
          <p className="text-xs text-gray-600">
            <span className="font-semibold text-purple-700">AI Analysis:</span>{' '}
            {group.metadata.llm_reasoning}
          </p>
        </div>
      )}
    </div>
  );
};

DuplicateGroupCard.propTypes = {
  fileId: PropTypes.string.isRequired,
  group: PropTypes.shape({
    group_id: PropTypes.string.isRequired,
    detection_type: PropTypes.string.isRequired,
    similarity_score: PropTypes.number.isRequired,
    columns: PropTypes.arrayOf(PropTypes.string).isRequired,
    metadata: PropTypes.object,
    recommendation: PropTypes.string.isRequired
  }).isRequired
};

export default DuplicateGroupCard;
