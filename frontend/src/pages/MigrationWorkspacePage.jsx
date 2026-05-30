/**
 * Migration Workspace Page - Main interface for reviewing ThoughtSpot to Power BI migration
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FileText,
  GitBranch,
  CheckCircle,
  Download,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import toast from 'react-hot-toast';

import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Tabs from '../components/common/Tabs';
import useMigrationStore from '../stores/migrationStore';
import migrationApi from '../services/migrationApi';
import { useMigrationWebSocket } from '../hooks/useMigrationWebSocket';

import MigrationStatsCards from '../components/migration/MigrationStatsCards';
import LogicGraphCanvas from '../components/migration/LogicGraphCanvas';
import CalculationsList from '../components/migration/CalculationsList';
import ValidationSummary from '../components/migration/ValidationSummary';
import DiscrepancyInspector from '../components/migration/DiscrepancyInspector';
import AgentTraceViewer from '../components/migration/AgentTraceViewer';
import ModelEnhancementAlert from '../components/migration/ModelEnhancementAlert';

export default function MigrationWorkspacePage() {
  const { migrationId } = useParams();
  const navigate = useNavigate();

  const {
    currentMigration,
    conversions,
    logicGraph,
    fidelityValidation,
    correctionHistory,
    actions,
    selectors,
  } = useMigrationStore();

  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  const shouldConnectWebSocket =
    Boolean(migrationId) &&
    Boolean(currentMigration) &&
    !['completed', 'failed'].includes(currentMigration.status);

  const { lastMessage } = useMigrationWebSocket(
    migrationId,
    shouldConnectWebSocket
  );

  const loadMigrationData = useCallback(async () => {
    if (!migrationId) return;

    setIsLoading(true);

    try {
      const [migration, workbooksData, calculationsData] = await Promise.all([
        migrationApi.getMigrationStatus(migrationId),
        migrationApi.getWorkbooks(migrationId),
        migrationApi.getCalculations(migrationId),
      ]);

      actions.setMigration(migration);

      actions.setWorkbooks(
        workbooksData?.workbooks ||
        workbooksData?.objects ||
        workbooksData?.files ||
        []
      );

      actions.setCalculations(
        calculationsData?.calculations ||
        calculationsData?.formulas ||
        []
      );

      const migrationStatus = migration?.status;

      if (['converting', 'validating', 'completed'].includes(migrationStatus)) {
        const [conversionsData, graphData] = await Promise.all([
          migrationApi.getConversions(migrationId),
          migrationApi.getLogicGraph(migrationId, 'reactflow'),
        ]);

        actions.setConversions(conversionsData?.conversions || []);
        actions.setLogicGraph(graphData || { nodes: [], edges: [], stats: {} });
      }

      if (migrationStatus === 'completed') {
        try {
          const [validationData, fidelityData, correctionData] =
            await Promise.all([
              migrationApi.getValidationResults(migrationId),
              migrationApi.getFidelityValidation(migrationId),
              migrationApi.getCorrectionHistory(migrationId),
            ]);

          actions.setValidationResults(
            validationData?.results ||
            validationData?.validation_results ||
            []
          );

          actions.setFidelityValidation(fidelityData || null);

          actions.setCorrectionHistory(
            correctionData?.correction_attempts ||
            correctionData?.corrections ||
            []
          );
        } catch (error) {
          console.warn('Fidelity validation data not available:', error);

          try {
            const validationData = await migrationApi.getValidationResults(
              migrationId
            );

            actions.setValidationResults(
              validationData?.results ||
              validationData?.validation_results ||
              []
            );
          } catch (validationError) {
            console.warn(
              'Basic validation data also unavailable:',
              validationError
            );
          }
        }
      }
    } catch (error) {
      console.error('Failed to load migration data:', error);
      toast.error('Failed to load migration data');
    } finally {
      setIsLoading(false);
    }
  }, [migrationId, actions]);

  useEffect(() => {
    loadMigrationData();
  }, [loadMigrationData]);

  useEffect(() => {
    if (!lastMessage) return;

    try {
      const data =
        typeof lastMessage.data === 'string'
          ? JSON.parse(lastMessage.data)
          : lastMessage.data;

      if (data?.type === 'progress') {
        actions.updateMigrationProgress(
          data.progress_percent,
          data.current_stage
        );

        if (data.status) {
          actions.updateMigrationStatus(data.status);
        }

        if (data.message) {
          toast.info(data.message);
        }
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, [lastMessage, actions]);

  const handleRefresh = async () => {
    await loadMigrationData();
    toast.success('Refreshed migration data');
  };

  const handleExport = () => {
    navigate(`/migration/${migrationId}/export`);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading migration data...</p>
        </div>
      </div>
    );
  }

  if (!currentMigration) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-600 mx-auto mb-4" />
          <p className="text-gray-900 font-semibold mb-2">
            Migration not found
          </p>
          <Button onClick={() => navigate('/migration')}>
            Start New Migration
          </Button>
        </div>
      </div>
    );
  }

  const stats = selectors.getConversionStats();

  const tabs = [
    { id: 'overview', label: 'Overview', icon: FileText },
    { id: 'logic-graph', label: 'Logic Graph', icon: GitBranch },
    { id: 'conversions', label: 'Conversions', icon: FileText },
    { id: 'validation', label: 'Validation', icon: CheckCircle },
    { id: 'fidelity', label: '100% Fidelity', icon: CheckCircle },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Migration Workspace
              </h1>

              <p className="text-sm text-gray-600 mt-1">
                ID: {migrationId} • Status:{' '}
                <span
                  className={`font-medium ${currentMigration.status === 'completed'
                      ? 'text-green-600'
                      : currentMigration.status === 'failed'
                        ? 'text-red-600'
                        : 'text-blue-600'
                    }`}
                >
                  {currentMigration.status || 'unknown'}
                </span>
              </p>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={handleRefresh}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>

              {currentMigration.status === 'completed' && (
                <Button onClick={handleExport}>
                  <Download className="w-4 h-4 mr-2" />
                  Export
                </Button>
              )}
            </div>
          </div>

          {currentMigration.status !== 'completed' &&
            currentMigration.status !== 'failed' && (
              <div className="mt-4">
                <div className="flex items-center justify-between text-sm text-gray-700 mb-2">
                  <span>{currentMigration.current_stage || 'Processing...'}</span>
                  <span>{currentMigration.progress_percent || 0}%</span>
                </div>

                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${currentMigration.progress_percent || 0}%`,
                    }}
                  />
                </div>
              </div>
            )}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="container mx-auto px-4 py-6">
        <MigrationStatsCards migration={currentMigration} stats={stats} />
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 pb-8">
        <Card className="p-6">
          <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

          <div className="mt-6">
            {activeTab === 'overview' && (
              <OverviewTab migration={currentMigration} stats={stats} />
            )}

            {activeTab === 'logic-graph' && (
              <div className="h-[600px]">
                <LogicGraphCanvas
                  graph={logicGraph || { nodes: [], edges: [], stats: {} }}
                  onNodeClick={(nodeId) => {
                    actions.selectCalculation(nodeId);
                    setActiveTab('conversions');
                  }}
                />
              </div>
            )}

            {activeTab === 'conversions' && (
              <CalculationsList
                conversions={Array.isArray(conversions) ? conversions : []}
                onSelect={(conversionId) =>
                  actions.selectConversion(conversionId)
                }
              />
            )}

            {activeTab === 'validation' && (
              <ValidationSummary migrationId={migrationId} />
            )}

            {activeTab === 'fidelity' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    Numerical Validation Results
                  </h3>

                  <DiscrepancyInspector
                    validationResults={fidelityValidation}
                  />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    Self-Healing Agent Activity
                  </h3>

                  <AgentTraceViewer
                    correctionHistory={
                      Array.isArray(correctionHistory)
                        ? correctionHistory
                        : []
                    }
                  />
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function OverviewTab({ migration, stats }) {
  const { migrationId } = useParams();

  return (
    <div className="space-y-6">
      <ModelEnhancementAlert migrationId={migrationId} />

      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Migration Summary
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Source Objects</p>
            <p className="text-2xl font-bold text-gray-900">
              {migration.object_count ||
                migration.workbook_count ||
                migration.file_count ||
                0}
            </p>
          </div>

          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Calculations</p>
            <p className="text-2xl font-bold text-gray-900">
              {migration.calculation_count || migration.formula_count || 0}
            </p>
          </div>

          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Conversions</p>
            <p className="text-2xl font-bold text-gray-900">
              {stats.total || 0}
            </p>
          </div>

          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Pass Rate</p>
            <p className="text-2xl font-bold text-green-600">
              {(stats.passRate || 0).toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {migration.status === 'completed' && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />

            <div>
              <p className="font-medium text-green-900 mb-1">
                Migration Completed Successfully
              </p>

              <p className="text-sm text-green-800">
                All calculations have been converted and validated. You can now
                export the Power BI artifacts.
              </p>
            </div>
          </div>
        </div>
      )}

      {migration.status === 'failed' && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />

            <div>
              <p className="font-medium text-red-900 mb-1">
                Migration Failed
              </p>

              <p className="text-sm text-red-800">
                {migration.error_message || 'An unexpected error occurred'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}