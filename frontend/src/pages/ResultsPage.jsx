import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useJobStore } from '../stores/jobStore.js';
import { useGraphStore } from '../stores/graphStore.js';
import { useUIStore } from '../stores/uiStore.js';
import { jobsApi } from '../services/jobsApi.js';
import { transformToReactFlow, countByConfidence } from '../utils/graphTransform.js';
import GraphCanvas from '../components/visualization/GraphCanvas.jsx';
import ExportPanel from '../components/export/ExportPanel.jsx';
import Button from '../components/common/Button.jsx';
import Spinner from '../components/common/Spinner.jsx';
import MigrationSidebar from '../components/migration/MigrationSidebar.jsx';
import useMigrationStore from '../stores/migrationStore.js';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const ResultsPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);

  const [isFilterCollapsed, setIsFilterCollapsed] = useState(() => {
    const saved = localStorage.getItem('results-filter-collapsed');
    return saved === 'true';
  });

  const toggleFilterCollapse = () => {
    setIsFilterCollapsed((prev) => {
      const newValue = !prev;
      localStorage.setItem('results-filter-collapsed', String(newValue));
      return newValue;
    });
  };

  const currentJob = useJobStore((state) => state.currentJob);
  const setResult = useJobStore((state) => state.actions.setResult);
  const showToast = useUIStore((state) => state.actions.showToast);
  const { currentMigration } = useMigrationStore();

  const isMigrationMode = !!currentMigration?.migration_id;

  const edges = useGraphStore((state) => state.edges);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const data = await jobsApi.getJobResult(jobId);

        if (data.status !== 'completed') {
          navigate(`/jobs/${jobId}/processing`);
          return;
        }

        setResult(data.result);

        const relationshipInclusion = {};

        if (data.result?.relationships) {
          data.result.relationships.forEach((rel) => {
            if (!rel.deleted && rel.relationship_id) {
              relationshipInclusion[rel.relationship_id] = {
                included: true,
              };
            }
          });
        }

        const { nodes: graphNodes, edges: graphEdges } = transformToReactFlow(
          data,
          relationshipInclusion
        );

        countByConfidence(graphEdges);

        useGraphStore.setState({
          nodes: graphNodes,
          edges: graphEdges,
          filteredEdges: graphEdges,
          relationshipInclusion,
        });

        setLoading(false);
      } catch (error) {
        console.error('Failed to fetch result:', error);
        showToast('Failed to load ThoughtSpot migration results', 'error');
        setLoading(false);
      }
    };

    fetchResult();
  }, [jobId, navigate, setResult, showToast]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Spinner size="xl" />
          <p className="text-gray-600 mt-4">
            Loading ThoughtSpot migration results...
          </p>
        </div>
      </div>
    );
  }

  const totalRelationships = edges.length;
  const fileCount = currentJob?.file_count || 0;

  if (isMigrationMode) {
    return (
      <div
        className="h-screen flex overflow-hidden"
        style={{ backgroundColor: '#e5e5e5' }}
      >
        <MigrationSidebar currentStep={2} />

        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="bg-white border-b border-gray-200 shadow-sm px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  ThoughtSpot Relationship Mapping
                </h1>

                <p className="text-sm text-gray-600 mt-1">
                  Found {totalRelationships} relationship
                  {totalRelationships !== 1 ? 's' : ''} across {fileCount} ThoughtSpot file
                  {fileCount !== 1 ? 's' : ''}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <ExportPanel />

                <Button onClick={() => navigate('/migration-wizard/field-mapping')}>
                  Next Step
                </Button>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-auto p-6">
            <div className="flex gap-6">
              {/* Collapsible Filter Sidebar */}
              <div
                className={`transition-all duration-300 ${isFilterCollapsed ? 'w-12' : 'w-80'
                  } flex-shrink-0`}
              >
                {isFilterCollapsed ? (
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-2 flex justify-center items-center">
                    <button
                      onClick={toggleFilterCollapse}
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex justify-center items-center"
                      aria-label="Expand filters"
                    >
                      <ChevronRight className="w-5 h-5 text-gray-600" />
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-gray-700">
                        Filters
                      </h3>

                      <button
                        onClick={toggleFilterCollapse}
                        className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors flex justify-center items-center"
                        aria-label="Collapse filters"
                      >
                        <ChevronLeft className="w-4 h-4 text-gray-600" />
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Main: Graph Canvas */}
              <div className="flex-1 min-w-0">
                <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden">
                  <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900">
                      ThoughtSpot to Power BI Relationship Diagram
                    </h2>
                  </div>

                  <div className="h-[700px] w-full">
                    <GraphCanvas />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Standalone ThoughtSpot metadata analysis layout
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <div className="bg-gradient-to-r from-white via-white to-gray-50 border-b border-gray-200 shadow-sm px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-600 to-primary-800 bg-clip-text text-transparent">
                ThoughtSpot Migration Results
              </h1>

              <div className="flex items-center gap-3 mt-2 text-sm text-gray-600">
                <div className="flex items-center gap-2">
                  <svg
                    className="w-4 h-4 text-gray-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                    />
                  </svg>

                  <span className="font-mono text-xs">
                    {jobId}
                  </span>
                </div>

                {fileCount > 0 && (
                  <>
                    <span className="text-gray-400">•</span>

                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                      <span>
                        {fileCount} ThoughtSpot file{fileCount !== 1 ? 's' : ''}
                      </span>
                    </div>

                    <span className="text-gray-400">•</span>

                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="font-semibold text-gray-900">
                        {totalRelationships} relationship
                        {totalRelationships !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <ExportPanel />

              <Button
                variant="secondary"
                size="md"
                onClick={() => navigate('/upload')}
              >
                <svg
                  className="w-4 h-4 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                New ThoughtSpot Analysis
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-6">
        <div className="flex gap-6">
          {/* Collapsible Filter Sidebar */}
          <div
            className={`transition-all duration-300 ${isFilterCollapsed ? 'w-12' : 'w-80'
              } flex-shrink-0`}
          >
            {isFilterCollapsed ? (
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-2 flex justify-center items-center">
                <button
                  onClick={toggleFilterCollapse}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex justify-center items-center"
                  aria-label="Expand filters"
                >
                  <ChevronRight className="w-5 h-5 text-gray-600" />
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">
                    Filters
                  </h3>

                  <button
                    onClick={toggleFilterCollapse}
                    className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors flex justify-center items-center"
                    aria-label="Collapse filters"
                  >
                    <ChevronLeft className="w-4 h-4 text-gray-600" />
                  </button>
                </div>

                {/* Help Card */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                      <svg
                        className="w-4 h-4 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    </div>

                    <h4 className="text-sm font-semibold text-blue-900">
                      How to Use
                    </h4>
                  </div>

                  <ul className="text-xs text-blue-800 space-y-2">
                    <li className="flex items-start gap-2">
                      <svg
                        className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 5l7 7-7 7"
                        />
                      </svg>

                      <span>Drag to pan the relationship graph</span>
                    </li>

                    <li className="flex items-start gap-2">
                      <svg
                        className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 5l7 7-7 7"
                        />
                      </svg>

                      <span>Scroll to zoom in/out</span>
                    </li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Main: Graph Canvas */}
          <div className="flex-1 min-w-0">
            <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 bg-gradient-to-r from-gray-50 to-white border-b border-gray-200">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center shadow-md">
                    <svg
                      className="w-5 h-5 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                      />
                    </svg>
                  </div>

                  <h2 className="text-lg font-semibold text-gray-900">
                    ThoughtSpot Relationship Diagram
                  </h2>
                </div>
              </div>

              {/* Graph Container */}
              <div className="h-[700px] w-full bg-gradient-to-br from-gray-50 to-white">
                <GraphCanvas />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResultsPage;