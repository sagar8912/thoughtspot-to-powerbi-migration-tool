import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Loader } from 'lucide-react';
import toast from 'react-hot-toast';

import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import useMigrationStore from '../../stores/migrationStore';
import useMigrationCacheStore from '../../stores/migrationCacheStore';
import migrationApi from '../../services/migrationApi';
import MigrationSidebar from '../../components/migration/MigrationSidebar';

import { useGraphStore } from '../../stores/graphStore';
import { transformToReactFlow } from '../../utils/graphTransform';
import GraphCanvas from '../../components/visualization/GraphCanvas';

export default function Page2ModelIntelligence() {
  const navigate = useNavigate();

  const { currentMigration } = useMigrationStore();
  const { loadModelIntelligence } = useMigrationCacheStore();

  const [isLoading, setIsLoading] = useState(true);
  const [tables, setTables] = useState([]);

  const loadData = useCallback(async () => {
    if (!currentMigration?.migration_id) {
      return;
    }

    setIsLoading(true);

    try {
      console.log('[Page2] Loading model intelligence and relationships...');

      const migrationId = currentMigration.migration_id;

      const [modelData, relationshipsData] = await Promise.all([
        loadModelIntelligence(migrationId),
        migrationApi.getSuggestedRelationships(migrationId),
      ]);

      const sourceTables = Array.isArray(modelData?.tables)
        ? modelData.tables
        : [];

      setTables(sourceTables);

      const filesForGraph = sourceTables.map((table) => ({
        file_name: table?.table_name || table?.display_name || 'Unknown Table',
        sheet_name: table?.table_name || table?.display_name || 'Unknown Table',
        row_count: table?.row_count || 0,
        column_count: Array.isArray(table?.column_details)
          ? table.column_details.length
          : 0,
        columns: Array.isArray(table?.column_details)
          ? table.column_details.map((column) => ({
            column_name: column?.name || 'Unknown Column',
            data_type: column?.data_type || column?.datatype || 'unknown',
          }))
          : [],
      }));

      const apiResult = {
        result: {
          files: filesForGraph,
          relationships: Array.isArray(relationshipsData?.relationships)
            ? relationshipsData.relationships
            : [],
        },
      };

      try {
        const { nodes: graphNodes, edges: graphEdges } = transformToReactFlow(
          apiResult,
          {}
        );

        useGraphStore.setState({
          nodes: graphNodes || [],
          edges: graphEdges || [],
          filteredEdges: graphEdges || [],
          relationshipInclusion: {},
        });
      } catch (graphError) {
        console.error('Failed to transform graph data:', graphError);

        useGraphStore.setState({
          nodes: [],
          edges: [],
          filteredEdges: [],
          relationshipInclusion: {},
        });

        toast.error('Failed to render relationship graph');
      }
    } catch (error) {
      console.error('Failed to load model intelligence:', error);
      toast.error('Failed to load data model');
    } finally {
      setIsLoading(false);
    }
  }, [currentMigration?.migration_id, loadModelIntelligence]);

  useEffect(() => {
    if (!currentMigration?.migration_id) {
      toast.error('No migration found. Please upload a ThoughtSpot file first.');
      navigate('/migration');
      return;
    }

    loadData();
  }, [currentMigration?.migration_id, navigate, loadData]);

  if (isLoading) {
    return (
      <div
        className="h-screen flex overflow-hidden"
        style={{ backgroundColor: '#e5e5e5' }}
      >
        <MigrationSidebar currentStep={2} />

        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
            <p className="text-gray-600">Loading data model...</p>
          </div>
        </div>
      </div>
    );
  }

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
                Data Model Configuration
              </h1>

              <p className="text-sm text-gray-600 mt-1">
                Visualizing relationships from ThoughtSpot source assets
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                onClick={() =>
                  navigate('/migration-wizard/data-understanding')
                }
              >
                Back
              </Button>

              <Button onClick={() => navigate('/migration-wizard/field-mapping')}>
                Next Step
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 flex flex-col min-h-0">
          {tables.length === 0 ? (
            <Card className="text-center py-12">
              <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />

              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                No Tables Found
              </h3>

              <p className="text-gray-600">
                No data tables were found in the source file. Please check the
                uploaded ThoughtSpot file.
              </p>
            </Card>
          ) : (
            <div className="flex-1 bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden flex flex-col min-h-0">
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-200 shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">
                  Relationship Diagram
                </h2>
              </div>

              <div className="flex-1 relative">
                <GraphCanvas />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}