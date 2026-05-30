/**
 * Page 5: Download & Complete
 * Final download page for ThoughtSpot to Power BI migration package
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Download,
  FileText,
  Package,
  CheckCircle,
} from 'lucide-react';
import toast from 'react-hot-toast';

import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import MigrationSidebar from '../../components/migration/MigrationSidebar';
import useMigrationStore from '../../stores/migrationStore';
import migrationApi from '../../services/migrationApi';

export default function Page5Recommendations() {
  const navigate = useNavigate();
  const { currentMigration } = useMigrationStore();

  const [downloading, setDownloading] = useState(false);

  const getMigrationId = useCallback(() => {
    return (
      currentMigration?.migration_id ||
      currentMigration?.job_id ||
      localStorage.getItem('last_job_id')
    );
  }, [currentMigration]);

  useEffect(() => {
    const migrationId = getMigrationId();

    if (!migrationId) {
      toast.error('No migration found. Please upload a ThoughtSpot file first.');
      navigate('/migration');
    }
  }, [getMigrationId, navigate]);

  const handleExportAll = async () => {
    const migrationId = getMigrationId();

    if (!migrationId) {
      toast.error('No migration found. Please upload a ThoughtSpot file first.');
      navigate('/migration');
      return;
    }

    try {
      setDownloading(true);

      await migrationApi.downloadAllArtifacts(migrationId);

      toast.success('Migration package downloaded successfully!');
    } catch (error) {
      console.error('Export failed:', error);

      const errorMessage =
        error.response?.data?.detail?.error?.message ||
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        'Failed to download migration package';

      toast.error(errorMessage);
    } finally {
      setDownloading(false);
    }
  };

  const handleBack = () => {
    navigate('/migration-wizard/formula-conversion');
  };

  const handleComplete = () => {
    toast.success('Migration completed successfully!');
    navigate('/');
  };

  return (
    <div
      className="h-screen flex overflow-hidden"
      style={{ backgroundColor: '#e5e5e5' }}
    >
      <MigrationSidebar currentStep={5} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 shadow-sm px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Download & Complete
              </h1>

              <p className="text-sm text-gray-600 mt-1">
                Your ThoughtSpot to Power BI migration package is ready.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button variant="secondary" onClick={handleBack}>
                Back
              </Button>

              <Button onClick={handleComplete}>
                Complete Migration
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Success Banner */}
            <Card className="bg-gradient-to-r from-green-50 to-blue-50 border-2 border-green-200">
              <div className="p-8 text-center">
                <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />

                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  Migration Analysis Complete!
                </h2>

                <p className="text-gray-700 max-w-2xl mx-auto">
                  Your ThoughtSpot assets have been successfully analyzed and
                  prepared for Power BI migration. Download the complete
                  migration package below.
                </p>
              </div>
            </Card>

            {/* Download Section */}
            <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-2 border-blue-200">
              <div className="p-8">
                <Download className="w-12 h-12 text-blue-600 mx-auto mb-4" />

                <h2 className="text-2xl font-bold text-gray-900 mb-4 text-center">
                  Download Complete Migration Package
                </h2>

                <p className="text-gray-700 mb-6 max-w-2xl mx-auto text-center">
                  Your package includes metadata, DAX conversion results,
                  validation outputs, and Power BI migration artifacts.
                </p>

                {/* Package Contents */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 max-w-3xl mx-auto text-left">
                  <div className="flex items-start gap-3 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
                    <FileText className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />

                    <div>
                      <p className="font-medium text-gray-900">
                        Excel Migration Report
                      </p>

                      <p className="text-sm text-gray-500">
                        migration_report.xlsx
                      </p>

                      <p className="text-xs text-gray-400 mt-1">
                        Metadata, calculations, mappings, and validation results
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
                    <Package className="w-5 h-5 text-purple-600 flex-shrink-0 mt-0.5" />

                    <div>
                      <p className="font-medium text-gray-900">
                        Power BI Semantic Model
                      </p>

                      <p className="text-sm text-gray-500">
                        model.bim
                      </p>

                      <p className="text-xs text-gray-400 mt-1">
                        Import or review using Tabular Editor
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
                    <FileText className="w-5 h-5 text-orange-600 flex-shrink-0 mt-0.5" />

                    <div>
                      <p className="font-medium text-gray-900">
                        Source Metadata
                      </p>

                      <p className="text-sm text-gray-500">
                        source_metadata.json
                      </p>

                      <p className="text-xs text-gray-400 mt-1">
                        Extracted ThoughtSpot worksheets, fields, formulas, and
                        objects
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
                    <FileText className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />

                    <div>
                      <p className="font-medium text-gray-900">
                        Instructions
                      </p>

                      <p className="text-sm text-gray-500">
                        README.txt
                      </p>

                      <p className="text-xs text-gray-400 mt-1">
                        Migration summary and Power BI import guide
                      </p>
                    </div>
                  </div>
                </div>

                {/* Power BI Instructions */}
                <div className="bg-white border border-blue-200 rounded-lg p-5 mb-6 max-w-3xl mx-auto">
                  <h3 className="font-semibold text-gray-900 mb-3">
                    How to use the generated model.bim
                  </h3>

                  <ol className="text-sm text-gray-700 space-y-2 list-decimal list-inside">
                    <li>Open Power BI Desktop with your target report.</li>
                    <li>Open Tabular Editor from the External Tools tab.</li>
                    <li>
                      Choose File &gt; Open &gt; From File and select model.bim.
                    </li>
                    <li>
                      Copy the generated calculation table or measures into your
                      connected Power BI model.
                    </li>
                    <li>Save changes to push them back to Power BI.</li>
                  </ol>
                </div>

                {/* Download Button */}
                <div className="text-center">
                  <Button
                    onClick={handleExportAll}
                    size="lg"
                    className="px-8"
                    icon={Download}
                    disabled={downloading}
                  >
                    {downloading
                      ? 'Downloading...'
                      : 'Download Complete Package (ZIP)'}
                  </Button>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}