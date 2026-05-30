import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  FolderOpen,
  Search,
  Link,
  Bot,
  BarChart3,
  FileText,
  Settings,
} from 'lucide-react';

const StageProgress = ({ progress, stage, status }) => {
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (status === 'running' || status === 'pending') {
      const startTime = Date.now();

      const interval = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [status]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;

    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const normalizeStage = (stageName) => {
    if (!stageName) return 'loading_files';

    const stageMap = {
      initializing: 'loading_files',
      uploading: 'loading_files',
      parsing: 'loading_files',
      parsing_files: 'loading_files',

      extracting_metadata: 'profiling_data',
      discovering_objects: 'profiling_data',
      profiling_data: 'profiling_data',

      extracting_relationships: 'detecting_relationships',
      detecting_relationships: 'detecting_relationships',

      extracting_formulas: 'llm_validation',
      converting_dax: 'llm_validation',
      llm_validation: 'llm_validation',

      validating: 'business_validation',
      business_validation: 'business_validation',

      generating_powerbi_model: 'generating_report',
      exporting_artifacts: 'generating_report',
      generating_report: 'generating_report',

      completed: 'generating_report',
      failed: 'generating_report',
    };

    return stageMap[stageName] || stageName;
  };

  const getStageMessage = (stageName) => {
    const normalizedStage = normalizeStage(stageName);

    const messages = {
      loading_files:
        'Reading ThoughtSpot files and validating metadata structure...',
      profiling_data:
        'Analyzing worksheets, answers, liveboards, columns, and object metadata...',
      detecting_relationships:
        'Finding joins, relationships, and dependency mappings across ThoughtSpot objects...',
      llm_validation:
        'Converting ThoughtSpot formulas into Power BI-compatible DAX...',
      business_validation:
        'Validating formula logic, relationships, and migration readiness...',
      generating_report:
        'Preparing your ThoughtSpot to Power BI migration report...',
    };

    return messages[normalizedStage] || 'Processing ThoughtSpot migration...';
  };

  const getStageIcon = (stageName) => {
    const normalizedStage = normalizeStage(stageName);
    const iconClass = 'w-6 h-6';

    const icons = {
      loading_files: <FolderOpen className={iconClass} />,
      profiling_data: <Search className={iconClass} />,
      detecting_relationships: <Link className={iconClass} />,
      llm_validation: <Bot className={iconClass} />,
      business_validation: <BarChart3 className={iconClass} />,
      generating_report: <FileText className={iconClass} />,
    };

    return icons[normalizedStage] || <Settings className={iconClass} />;
  };

  const getStageLabel = (stageName) => {
    const normalizedStage = normalizeStage(stageName);

    const labels = {
      loading_files: 'Loading ThoughtSpot Files',
      profiling_data: 'Analyzing Metadata',
      detecting_relationships: 'Mapping Relationships',
      llm_validation: 'Converting Formulas',
      business_validation: 'Validating Migration',
      generating_report: 'Generating Report',
    };

    return labels[normalizedStage] || 'Processing';
  };

  const getStageOrder = (stageName) => {
    const normalizedStage = normalizeStage(stageName);

    const order = {
      loading_files: 1,
      profiling_data: 2,
      detecting_relationships: 3,
      llm_validation: 4,
      business_validation: 5,
      generating_report: 6,
    };

    return order[normalizedStage] || 0;
  };

  const stages = [
    'loading_files',
    'profiling_data',
    'detecting_relationships',
    'llm_validation',
    'business_validation',
    'generating_report',
  ];

  const safeProgress = Math.max(0, Math.min(100, Number(progress) || 0));
  const normalizedCurrentStage = normalizeStage(stage);

  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset =
    circumference - (safeProgress / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center py-8 animate-fade-in">
      {/* Circular Progress */}
      <div className="relative">
        <svg className="transform -rotate-90" width="180" height="180">
          {/* Background circle */}
          <circle
            cx="90"
            cy="90"
            r={radius}
            stroke="#e5e7eb"
            strokeWidth="12"
            fill="none"
          />

          {/* Progress circle */}
          <circle
            cx="90"
            cy="90"
            r={radius}
            stroke="url(#gradient)"
            strokeWidth="12"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-500 ease-out"
          />

          {/* Gradient definition */}
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="#2563eb" />
            </linearGradient>
          </defs>
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold text-gray-900">
            {Math.round(safeProgress)}%
          </span>

          <span className="text-xs text-gray-500 mt-1">
            {formatTime(elapsedTime)} elapsed
          </span>
        </div>
      </div>

      {/* Stage information */}
      <div className="mt-8 text-center max-w-md">
        <div className="flex items-center justify-center gap-2 mb-3">
          <span className="text-primary-600">
            {getStageIcon(normalizedCurrentStage)}
          </span>

          <h3 className="text-lg font-semibold text-gray-900">
            {getStageLabel(normalizedCurrentStage)}
          </h3>
        </div>

        <p className="text-gray-600">
          {getStageMessage(normalizedCurrentStage)}
        </p>
      </div>

      {/* Processing stages indicator */}
      <div className="mt-8 w-full max-w-lg">
        <div className="flex justify-between items-center">
          {stages.map((stageName, index) => {
            const isActive = stageName === normalizedCurrentStage;
            const isPassed =
              getStageOrder(normalizedCurrentStage) > getStageOrder(stageName);

            return (
              <div key={stageName} className="flex-1 flex items-center">
                <div className="flex flex-col items-center flex-1">
                  <div
                    className={`w-3 h-3 rounded-full transition-all duration-300 ${isPassed
                        ? 'bg-green-500'
                        : isActive
                          ? 'bg-primary-600 animate-pulse'
                          : 'bg-gray-300'
                      }`}
                    title={getStageLabel(stageName)}
                  />
                </div>

                {index < stages.length - 1 && (
                  <div
                    className={`h-0.5 flex-1 transition-all duration-300 ${isPassed ? 'bg-green-500' : 'bg-gray-300'
                      }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        <div className="flex justify-between mt-2 text-[10px] text-gray-500">
          <span>Files</span>
          <span>Metadata</span>
          <span>Relations</span>
          <span>DAX</span>
          <span>Validate</span>
          <span>Report</span>
        </div>
      </div>
    </div>
  );
};

StageProgress.propTypes = {
  progress: PropTypes.number.isRequired,
  stage: PropTypes.string,
  status: PropTypes.string,
};

export default StageProgress;