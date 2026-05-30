import { useState } from 'react';
import { useJobStore } from '../../stores/jobStore.js';
import { useGraphStore } from '../../stores/graphStore.js';
import { useUIStore } from '../../stores/uiStore.js';
import {
  exportJSON,
  filterResultsByVisibility,
  generateFilename,
} from '../../utils/export.js';
import Button from '../common/Button.jsx';

const ExportPanel = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  const currentJob = useJobStore((state) => state.currentJob);
  const filteredEdges = useGraphStore((state) => state.filteredEdges);
  const confidenceFilter = useGraphStore((state) => state.confidenceFilter);
  const showToast = useUIStore((state) => state.actions.showToast);

  const handleExportRaw = async () => {
    setExporting(true);

    try {
      const fullResult = {
        job_id: currentJob?.job_id,
        status: currentJob?.status,
        completed_at: currentJob?.completed_at,
        source: 'thoughtspot',
        target: 'powerbi',
        report_type: 'thoughtspot_powerbi_full_migration_report',
        result: currentJob?.result,
      };

      const filename = generateFilename(
        `thoughtspot_powerbi_full_report_${currentJob?.job_id || 'export'}`
      );

      const success = exportJSON(fullResult, filename);

      if (success) {
        showToast('Full ThoughtSpot migration report downloaded successfully', 'success');
        setIsOpen(false);
      } else {
        showToast('Failed to export ThoughtSpot migration report', 'error');
      }
    } catch (error) {
      showToast(`Export failed: ${error.message}`, 'error');
    } finally {
      setExporting(false);
    }
  };

  const handleExportFiltered = async () => {
    setExporting(true);

    try {
      const fullResult = {
        job_id: currentJob?.job_id,
        status: currentJob?.status,
        completed_at: currentJob?.completed_at,
        source: 'thoughtspot',
        target: 'powerbi',
        report_type: 'thoughtspot_powerbi_filtered_relationship_report',
        result: currentJob?.result,
      };

      const filteredResult = filterResultsByVisibility(
        fullResult,
        filteredEdges,
        confidenceFilter
      );

      if (!filteredResult) {
        showToast('No ThoughtSpot relationship data to export', 'error');
        return;
      }

      const filename = generateFilename(
        `thoughtspot_powerbi_filtered_report_${currentJob?.job_id || 'export'}`
      );

      const success = exportJSON(filteredResult, filename);

      if (success) {
        showToast('Filtered ThoughtSpot migration results downloaded successfully', 'success');
        setIsOpen(false);
      } else {
        showToast('Failed to export filtered migration results', 'error');
      }
    } catch (error) {
      showToast(`Export failed: ${error.message}`, 'error');
    } finally {
      setExporting(false);
    }
  };

  const visibleCount = filteredEdges.length;

  const totalCount =
    (confidenceFilter.HIGH?.count || 0) +
    (confidenceFilter.MEDIUM?.count || 0) +
    (confidenceFilter.LOW?.count || 0);

  return (
    <div className="relative">
      <Button
        variant="secondary"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
          />
        </svg>
        Export
      </Button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-xl border border-gray-200 z-20 animate-fade-in">
            <div className="p-4 border-b border-gray-200">
              <h3 className="text-sm font-semibold text-gray-900">
                Export Options
              </h3>

              <p className="text-xs text-gray-500 mt-1">
                Download ThoughtSpot to Power BI migration results as JSON
              </p>
            </div>

            <div className="p-4 space-y-3">
              {/* Filtered Export */}
              <button
                onClick={handleExportFiltered}
                disabled={exporting || visibleCount === 0}
                className="w-full text-left p-3 rounded-lg border-2 border-primary-200 hover:border-primary-400 hover:bg-primary-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-primary-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
                      />
                    </svg>
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      Filtered Migration Results
                    </p>

                    <p className="text-xs text-gray-600 mt-1">
                      Export only visible ThoughtSpot relationships ({visibleCount} of {totalCount})
                    </p>

                    <p className="text-xs text-gray-500 mt-1">
                      Includes selected filter metadata
                    </p>
                  </div>
                </div>
              </button>

              {/* Raw Export */}
              <button
                onClick={handleExportRaw}
                disabled={exporting}
                className="w-full text-left p-3 rounded-lg border-2 border-gray-200 hover:border-gray-400 hover:bg-gray-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-gray-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      Full Migration Report
                    </p>

                    <p className="text-xs text-gray-600 mt-1">
                      Complete ThoughtSpot to Power BI API response with all data
                    </p>

                    <p className="text-xs text-gray-500 mt-1">
                      Includes all {totalCount} relationship
                      {totalCount !== 1 ? 's' : ''}
                    </p>
                  </div>
                </div>
              </button>
            </div>

            <div className="p-3 bg-gray-50 border-t border-gray-200 rounded-b-lg">
              <p className="text-xs text-gray-500 text-center">
                Files download in JSON format
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ExportPanel;