import PropTypes from 'prop-types';
import { AlertTriangle } from 'lucide-react';
import usePreviewStore from '../../stores/previewStore';

const CompactDuplicateAlert = ({ group, fileId }) => {
  const { isColumnMarkedForDeletion, toggleColumnDeletion } = usePreviewStore();

  // Determine colors based on detection type
  const isSemantic = group.detection_type === 'semantic_overlap';
  const bgColor = isSemantic ? 'bg-indigo-50' : 'bg-yellow-50';
  const borderColor = isSemantic ? 'border-indigo-300' : 'border-yellow-300';
  const iconColor = isSemantic ? 'text-indigo-600' : 'text-yellow-600';
  const textColor = isSemantic ? 'text-indigo-900' : 'text-yellow-900';
  const recommendationColor = isSemantic ? 'text-indigo-700' : 'text-yellow-700';

  return (
    <div className={`${bgColor} border ${borderColor} rounded-lg p-4`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className={`w-5 h-5 ${iconColor} flex-shrink-0 mt-0.5`} />
        <div className="flex-1">
          <h4 className={`text-sm font-semibold ${textColor} mb-2`}>
            {group.detection_type.replace(/_/g, ' ')} - {Math.round(group.similarity_score)}% similar
            {isSemantic && <span className="ml-2 text-xs font-normal">(LLM Validated)</span>}
          </h4>

          {/* Columns in horizontal layout */}
          <div className="flex items-center gap-2 flex-wrap">
            {group.columns.map((columnName, index) => {
              const isMarked = isColumnMarkedForDeletion(fileId, columnName);

              return (
                <button
                  key={index}
                  onClick={() => toggleColumnDeletion(fileId, columnName)}
                  className={`
                    inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors
                    ${isMarked
                      ? 'bg-red-100 text-red-700 border border-red-300'
                      : 'bg-white text-gray-900 border border-gray-300 hover:bg-gray-50'
                    }
                  `}
                >
                  <span className={isMarked ? 'line-through' : ''}>{columnName}</span>
                  <span className={`
                    text-xs px-1.5 py-0.5 rounded
                    ${isMarked ? 'bg-red-200 text-red-800' : 'bg-emerald-100 text-emerald-700'}
                  `}>
                    {isMarked ? 'Delete' : 'Keep'}
                  </span>
                </button>
              );
            })}
          </div>

          {group.recommendation && (
            <p className={`text-xs ${recommendationColor} mt-2`}>
              <strong>Recommendation:</strong> {group.recommendation}
            </p>
          )}

          {/* Show LLM reasoning for semantic duplicates */}
          {isSemantic && group.metadata?.llm_reasoning && (
            <p className="text-xs text-indigo-600 mt-2 italic">
              <strong>AI Analysis:</strong> {group.metadata.llm_reasoning}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

CompactDuplicateAlert.propTypes = {
  group: PropTypes.shape({
    group_id: PropTypes.string,
    detection_type: PropTypes.string.isRequired,
    similarity_score: PropTypes.number.isRequired,
    columns: PropTypes.arrayOf(PropTypes.string).isRequired,
    recommendation: PropTypes.string
  }).isRequired,
  fileId: PropTypes.string.isRequired
};

export default CompactDuplicateAlert;
