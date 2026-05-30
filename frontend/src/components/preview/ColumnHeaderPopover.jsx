import { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Info, Trash2, Hash, FileText, Calendar, CheckSquare, AlertCircle } from 'lucide-react';
import usePreviewStore from '../../stores/previewStore';

const ColumnHeaderPopover = ({ column, fileId }) => {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef(null);
  const { isColumnMarkedForDeletion, toggleColumnDeletion } = usePreviewStore();

  const isMarked = isColumnMarkedForDeletion(fileId, column.name);

  // Close popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Calculate percentages
  const totalCount = column.null_count + column.unique_count;
  const uniquePercentage = totalCount > 0 ? ((column.unique_count / totalCount) * 100).toFixed(1) : 0;
  const nullPercentage = totalCount > 0 ? ((column.null_count / totalCount) * 100).toFixed(1) : 0;

  // Type icon and color
  const type = column.data_type?.toLowerCase();
  let TypeIcon, typeColor;

  switch (type) {
    case 'string':
    case 'text':
      TypeIcon = FileText;
      typeColor = 'text-blue-600 bg-blue-50';
      break;
    case 'int':
    case 'float':
    case 'number':
      TypeIcon = Hash;
      typeColor = 'text-green-600 bg-green-50';
      break;
    case 'datetime':
    case 'date':
      TypeIcon = Calendar;
      typeColor = 'text-purple-600 bg-purple-50';
      break;
    case 'boolean':
    case 'bool':
      TypeIcon = CheckSquare;
      typeColor = 'text-orange-600 bg-orange-50';
      break;
    default:
      TypeIcon = AlertCircle;
      typeColor = 'text-gray-600 bg-gray-50';
  }

  return (
    <div className="relative inline-block" ref={popoverRef}>
      {/* Header Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center gap-1 px-2 py-1.5 rounded transition-colors
          ${isMarked ? 'bg-red-100 text-red-700' : 'hover:bg-gray-100'}
          ${isOpen ? 'bg-gray-100' : ''}
        `}
      >
        <span className={`text-xs font-semibold ${isMarked ? 'line-through' : ''}`}>
          {column.name}
        </span>
        <Info className="w-3 h-3 text-gray-400" />
      </button>

      {/* Popover */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-white rounded-lg shadow-xl border border-gray-200 z-50">
          <div className="p-3 space-y-3">
            {/* Type */}
            <div>
              <p className="text-[10px] text-gray-500 uppercase font-semibold mb-1">Type</p>
              <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${typeColor}`}>
                <TypeIcon className="w-3 h-3" />
                {type}
              </div>
            </div>

            {/* Unique Percentage */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <p className="text-[10px] text-gray-500 uppercase font-semibold">Unique</p>
                <span className="text-xs font-bold text-gray-900">{uniquePercentage}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full ${
                    uniquePercentage >= 80 ? 'bg-emerald-500' : uniquePercentage >= 50 ? 'bg-amber-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${uniquePercentage}%` }}
                />
              </div>
              <p className="text-[10px] text-gray-500 mt-0.5">{column.unique_count.toLocaleString()} values</p>
            </div>

            {/* Null Percentage */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <p className="text-[10px] text-gray-500 uppercase font-semibold">Nulls</p>
                <span className={`text-xs font-bold ${column.null_count > 0 ? 'text-orange-600' : 'text-gray-900'}`}>
                  {nullPercentage}%
                </span>
              </div>
              {column.null_count > 0 && (
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full ${
                      nullPercentage < 5 ? 'bg-emerald-500' : nullPercentage < 20 ? 'bg-amber-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${nullPercentage}%` }}
                  />
                </div>
              )}
              <p className="text-[10px] text-gray-500 mt-0.5">{column.null_count.toLocaleString()} nulls</p>
            </div>
          </div>

          {/* Delete Button */}
          <div className="border-t border-gray-200 p-2">
            <button
              onClick={() => {
                toggleColumnDeletion(fileId, column.name);
                setIsOpen(false);
              }}
              className={`
                w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors
                ${isMarked
                  ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  : 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200'
                }
              `}
            >
              <Trash2 className="w-3 h-3" />
              {isMarked ? 'Keep Column' : 'Delete Column'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

ColumnHeaderPopover.propTypes = {
  column: PropTypes.shape({
    name: PropTypes.string.isRequired,
    data_type: PropTypes.string.isRequired,
    null_count: PropTypes.number.isRequired,
    unique_count: PropTypes.number.isRequired
  }).isRequired,
  fileId: PropTypes.string.isRequired
};

export default ColumnHeaderPopover;
