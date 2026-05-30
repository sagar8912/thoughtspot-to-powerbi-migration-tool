/**
 * Migration Upload Page - Upload ThoughtSpot files to start migration
 */
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload,
  FileSpreadsheet,
  AlertCircle,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import toast from 'react-hot-toast';

import FileUploadZone from '../components/upload/FileUploadZone';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import migrationApi from '../services/migrationApi';
import useMigrationStore from '../stores/migrationStore';
import { config } from '../config';

const ALLOWED_EXTENSIONS = [
  '.tml',
  '.yaml',
  '.yml',
  '.json',
  '.zip',
  '.csv',
  '.xlsx',
  '.xls',
];

const ACCEPTED_FILE_TYPES = ALLOWED_EXTENSIONS.join(',');

function isAllowedThoughtSpotFile(fileName) {
  const lowerName = fileName.toLowerCase();
  return ALLOWED_EXTENSIONS.some((extension) => lowerName.endsWith(extension));
}

function getApiErrorMessage(error) {
  return (
    error.response?.data?.detail ||
    error.response?.data?.error?.message ||
    error.response?.data?.message ||
    error.message ||
    'Something went wrong. Please try again.'
  );
}

export default function MigrationUploadPage() {
  const navigate = useNavigate();
  const { actions } = useMigrationStore();

  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [isPolling, setIsPolling] = useState(false);
  const [currentStatus, setCurrentStatus] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [migrationId, setMigrationId] = useState(null);

  const pollingIntervalRef = useRef(null);

  useEffect(() => {
    if (!isPolling || !migrationId) {
      return undefined;
    }

    pollingIntervalRef.current = setInterval(async () => {
      try {
        const statusData = await migrationApi.getMigrationStatus(migrationId);

        setCurrentStatus(statusData.status);

        actions.updateMigrationStatus(statusData.status);

        if (statusData.progress_percent !== undefined || statusData.current_stage) {
          actions.updateMigrationProgress(
            statusData.progress_percent,
            statusData.current_stage
          );
        }

        if (statusData.current_stage) {
          setStatusMessage(statusData.current_stage);
        } else {
          setStatusMessage(`Status: ${statusData.status}...`);
        }

        if (statusData.status === 'completed') {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;

          setIsPolling(false);
          setIsUploading(false);

          actions.updateMigrationStatus('completed');

          toast.success('Migration analysis complete!');
          navigate('/migration-wizard/data-understanding');
        }

        if (statusData.status === 'failed') {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;

          setIsPolling(false);
          setIsUploading(false);

          actions.updateMigrationStatus('failed');

          toast.error(
            statusData.error_message || 'Migration failed during processing'
          );
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, config.pollInterval || 3000);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isPolling, migrationId, navigate, actions]);

  const handleFilesSelected = (files) => {
    const incomingFiles = Array.from(files || []);

    if (incomingFiles.length > config.maxFiles) {
      toast.error(`You can upload maximum ${config.maxFiles} files at once.`);
      return;
    }

    const validFiles = incomingFiles.filter((file) => {
      const isAllowedExtension = isAllowedThoughtSpotFile(file.name);
      const isAllowedSize = file.size <= config.maxFileSize;

      if (!isAllowedExtension) {
        return false;
      }

      if (!isAllowedSize) {
        toast.error(`${file.name} is larger than 100MB.`);
        return false;
      }

      return true;
    });

    if (validFiles.length !== incomingFiles.length) {
      toast.error(
        'Only .tml, .yaml, .yml, .json, .zip, .csv, .xlsx, and .xls files under 100MB are supported.'
      );
    }

    setSelectedFiles(validFiles);
  };

  const handleRemoveFile = (index) => {
    if (isUploading) return;

    setSelectedFiles((previousFiles) =>
      previousFiles.filter((_, fileIndex) => fileIndex !== index)
    );
  };

  const handleStartMigration = async () => {
    if (selectedFiles.length === 0) {
      toast.error('Please select at least one ThoughtSpot file');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setCurrentStatus(null);
    setStatusMessage('Uploading ThoughtSpot files...');

    try {
      const response = await migrationApi.createMigration(
        selectedFiles,
        (progress) => {
          setUploadProgress(progress);
        }
      );

      const newMigrationId = response.migration_id || response.job_id;

      if (!newMigrationId) {
        throw new Error('Backend did not return migration_id or job_id.');
      }

      localStorage.setItem('last_job_id', newMigrationId);

      toast.success('Files uploaded! Starting analysis...');
      setStatusMessage('Initializing ThoughtSpot analysis...');

      actions.setMigration({
        migration_id: newMigrationId,
        job_id: response.job_id || newMigrationId,
        status: response.status || 'pending',
        object_count:
          response.object_count || response.file_count || selectedFiles.length,
      });

      setMigrationId(newMigrationId);
      setIsPolling(true);
    } catch (error) {
      console.error('Upload failed:', error);

      toast.error(getApiErrorMessage(error));

      setIsUploading(false);
      setIsPolling(false);
      setUploadProgress(0);
      setCurrentStatus(null);
      setStatusMessage('');
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          ThoughtSpot to Power BI Migration
        </h1>

        <p className="text-gray-600">
          Upload your ThoughtSpot metadata files to start AI-powered Power BI
          migration.
        </p>
      </div>

      {/* Info Card */}
      <Card className="mb-6 bg-blue-50 border-blue-200">
        <div className="flex gap-3">
          <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />

          <div className="text-sm text-blue-900">
            <p className="font-medium mb-1">What happens next:</p>

            <ol className="list-decimal list-inside space-y-1 text-blue-800">
              <li>
                AI analyzes your ThoughtSpot files and extracts worksheets,
                answers, and liveboards.
              </li>
              <li>
                Formulas, joins, relationships, and dependencies are mapped.
              </li>
              <li>
                ThoughtSpot formulas are converted into Power BI-compatible DAX.
              </li>
              <li>
                Conversions are validated for migration readiness.
              </li>
              <li>
                You review and export ready-to-use Power BI migration artifacts.
              </li>
            </ol>
          </div>
        </div>
      </Card>

      {/* Upload Zone */}
      <Card className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Select ThoughtSpot Files
        </h2>

        <FileUploadZone
          onFilesSelected={handleFilesSelected}
          accept={ACCEPTED_FILE_TYPES}
          maxFiles={config.maxFiles}
          title="Upload ThoughtSpot Files"
          description="Drag and drop or browse to choose .tml, .yaml, .json, .zip, .csv, or Excel files"
          disabled={isUploading}
        />

        {selectedFiles.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">
              Selected Files ({selectedFiles.length})
            </h3>

            <div className="space-y-2">
              {selectedFiles.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
                >
                  <div className="flex items-center gap-3">
                    <FileSpreadsheet className="w-5 h-5 text-blue-600" />

                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {file.name}
                      </p>

                      <p className="text-xs text-gray-500">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>

                  {!isUploading && (
                    <button
                      type="button"
                      onClick={() => handleRemoveFile(index)}
                      className="text-sm text-red-600 hover:text-red-700 font-medium"
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {isUploading && (
          <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-100">
            <div className="flex items-center justify-between text-sm text-blue-900 mb-2">
              <span className="font-medium flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                {statusMessage}
              </span>

              <span>{isPolling ? currentStatus || 'processing' : `${uploadProgress}%`}</span>
            </div>

            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              {isPolling ? (
                <div className="bg-blue-600 h-2 rounded-full w-1/3 animate-pulse" />
              ) : (
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              )}
            </div>

            {isPolling && (
              <p className="text-xs text-blue-700 mt-2">
                This may take a few minutes depending on file size and
                ThoughtSpot object complexity. Please do not close this page.
              </p>
            )}
          </div>
        )}
      </Card>

      {/* Action Buttons */}
      <div className="flex justify-between items-center">
        <Button
          variant="ghost"
          onClick={() => navigate('/')}
          disabled={isUploading}
        >
          Cancel
        </Button>

        <Button
          onClick={handleStartMigration}
          disabled={selectedFiles.length === 0 || isUploading}
          className="gap-2"
        >
          {isUploading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              Start Migration
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </Button>
      </div>

      {/* Feature Highlights */}
      <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-6">
          <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
            <FileSpreadsheet className="w-6 h-6 text-blue-600" />
          </div>

          <h3 className="font-semibold text-gray-900 mb-2">
            Smart Conversion
          </h3>

          <p className="text-sm text-gray-600">
            AI analyzes ThoughtSpot formulas, visual context, and metadata to
            generate optimized DAX formulas.
          </p>
        </Card>

        <Card className="p-6">
          <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
            <svg
              className="w-6 h-6 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>

          <h3 className="font-semibold text-gray-900 mb-2">
            Validated Results
          </h3>

          <p className="text-sm text-gray-600">
            Every conversion is checked for migration readiness before exporting
            Power BI artifacts.
          </p>
        </Card>

        <Card className="p-6">
          <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
            <Upload className="w-6 h-6 text-purple-600" />
          </div>

          <h3 className="font-semibold text-gray-900 mb-2">
            Ready to Deploy
          </h3>

          <p className="text-sm text-gray-600">
            Export Power BI-compatible outputs including DAX measures, semantic
            model metadata, and reports.
          </p>
        </Card>
      </div>
    </div>
  );
}