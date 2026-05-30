import { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Info, Trash2, X, Hash, FileText, Calendar, CheckSquare, AlertCircle } from 'lucide-react';
import { createPortal } from 'react-dom';
import usePreviewStore from '../../stores/previewStore';

const EnhancedColumnHeader = ({ column, fileId }) => {
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const popoverRef = useRef(null);
  const buttonRef = useRef(null);
  const { isColumnMarkedForDeletion, toggleColumnDeletion } = usePreviewStore();

  const isMarked = isColumnMarkedForDeletion(fileId, column.name);

  // Close popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target) &&
          buttonRef.current && !buttonRef.current.contains(event.target)) {
        setIsPopoverOpen(false);
      }
    };

    if (isPopoverOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isPopoverOpen]);

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

  const handleDeleteClick = () => {
    setIsPopoverOpen(false);
    setIsModalOpen(true);
  };

  const confirmDelete = () => {
    toggleColumnDeletion(fileId, column.name);
    setIsModalOpen(false);
  };

  // Popover content (using portal to avoid clipping)
  const popoverContent = isPopoverOpen && buttonRef.current && createPortal(
    <div
      ref={popoverRef}
      className="absolute bg-white rounded-lg shadow-xl border border-gray-200 w-56 z-[9999]"
      style={{
        top: buttonRef.current.getBoundingClientRect().bottom + window.scrollY + 4,
        left: buttonRef.current.getBoundingClientRect().left + window.scrollX,
      }}
    >
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
    </div>,
    document.body
  );

  // Confirmation Modal
  const modal = isModalOpen && createPortal(
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[10000]">
      <div className="bg-white rounded-lg shadow-2xl max-w-md w-full mx-4">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Confirm Deletion</h3>
            <button
              onClick={() => setIsModalOpen(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <p className="text-sm text-gray-600 mb-6">
            Are you sure you want to {isMarked ? 'keep' : 'delete'} the column <strong>{column.name}</strong>?
            {!isMarked && ' This action can be undone before processing.'}
          </p>
          <div className="flex gap-3 justify-end">
            <button
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={confirmDelete}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                isMarked
                  ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                  : 'bg-red-600 text-white hover:bg-red-700'
              }`}
            >
              {isMarked ? 'Keep Column' : 'Delete Column'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );

  return (
    <>
      <div ref={buttonRef} className="flex items-center justify-center gap-2">
        <span className={`text-xs font-semibold ${isMarked ? 'line-through text-red-600' : 'text-slate-900'}`}>
          {column.name}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsPopoverOpen(!isPopoverOpen)}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
            title="Column Info"
          >
            <Info className="w-3.5 h-3.5 text-slate-500" />
          </button>
          <button
            onClick={handleDeleteClick}
            className="p-1 hover:bg-gray-100 rounded transition-colors group"
            title={isMarked ? 'Keep Column' : 'Delete Column'}
          >
            <Trash2 className={`w-3.5 h-3.5 transition-colors ${
              isMarked ? 'text-emerald-500' : 'text-slate-500 group-hover:text-red-500'
            }`} />
          </button>
        </div>
      </div>

      {popoverContent}
      {modal}
    </>
  );
};

EnhancedColumnHeader.propTypes = {
  column: PropTypes.shape({
    name: PropTypes.string.isRequired,
    data_type: PropTypes.string.isRequired,
    null_count: PropTypes.number.isRequired,
    unique_count: PropTypes.number.isRequired
  }).isRequired,
  fileId: PropTypes.string.isRequired
};

export default EnhancedColumnHeader;
