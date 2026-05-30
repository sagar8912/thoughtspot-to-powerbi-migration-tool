import PropTypes from 'prop-types';
import { BaseEdge, getSmoothStepPath } from 'reactflow';

/**
 * Custom Relationship Edge Component
 * Displays relationship connections between columns with confidence-based styling
 */
const RelationshipEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  style
}) => {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 8
  });

  const confidenceLevel = data?.relationship?.confidence_level || 'LOW';

  // Get confidence badge styling
  const getBadgeStyle = () => {
    switch (confidenceLevel) {
      case 'HIGH':
        return 'bg-green-100 text-green-700 border-green-300';
      case 'MEDIUM':
        return 'bg-orange-100 text-orange-700 border-orange-300';
      case 'LOW':
        return 'bg-gray-100 text-gray-700 border-gray-300';
      default:
        return 'bg-gray-100 text-gray-600 border-gray-300';
    }
  };

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />

      {/* Edge Label with Confidence Badge */}
      <foreignObject
        width={120}
        height={40}
        x={labelX - 60}
        y={labelY - 20}
        className="overflow-visible"
      >
        <div className="flex items-center justify-center">
          <div
            className={`
              px-2 py-1 rounded text-xs font-medium border
              ${getBadgeStyle()}
              shadow-sm
              cursor-pointer
              hover:shadow-md
              transition-shadow
            `}
            title={`${confidenceLevel} confidence relationship`}
          >
            {confidenceLevel}
          </div>
        </div>
      </foreignObject>
    </>
  );
};

RelationshipEdge.propTypes = {
  id: PropTypes.string.isRequired,
  sourceX: PropTypes.number.isRequired,
  sourceY: PropTypes.number.isRequired,
  targetX: PropTypes.number.isRequired,
  targetY: PropTypes.number.isRequired,
  sourcePosition: PropTypes.string,
  targetPosition: PropTypes.string,
  data: PropTypes.shape({
    relationship: PropTypes.shape({
      confidence_level: PropTypes.string
    }),
    confidenceLevel: PropTypes.string
  }),
  markerEnd: PropTypes.string,
  style: PropTypes.object
};

export default RelationshipEdge;
