/**
 * Migration Sidebar - Shared navigation component for ThoughtSpot migration wizard
 *
 * Shows all 5 migration steps with progress tracking
 */
import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import {
  Grid,
  Layout,
  Code,
  Database,
  CheckCircle,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

const MIGRATION_STEPS = [
  {
    id: 1,
    name: 'Source Dashboard Exploration',
    icon: Database,
    path: '/migration-wizard/data-understanding'
  },
  {
    id: 2,
    name: 'Data Model Configuration',
    icon: Grid,
    path: '/migration-wizard/model-intelligence'
  },
  {
    id: 3,
    name: 'Calculated Fields Mapping',
    icon: Layout,
    path: '/migration-wizard/field-mapping'
  },
  {
    id: 4,
    name: 'DAX Conversion',
    icon: Code,
    path: '/migration-wizard/formula-conversion'
  },
  {
    id: 5,
    name: 'Review & Export',
    icon: CheckCircle,
    path: '/migration-wizard/review'
  }
];

export default function MigrationSidebar({ currentStep = 1 }) {
  const navigate = useNavigate();

  const [isCollapsed, setIsCollapsed] = useState(() => {
    const saved = localStorage.getItem('migration-sidebar-collapsed');
    return saved === 'true';
  });

  useEffect(() => {
    localStorage.setItem('migration-sidebar-collapsed', isCollapsed);
  }, [isCollapsed]);

  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed);
  };

  const handleStepClick = (step) => {
    navigate(step.path);
  };

  return (
    <div
      className={`${isCollapsed ? 'w-16' : 'w-64'
        } bg-white border-r border-gray-200 flex flex-col transition-all duration-300 ease-in-out`}
    >
      {/* Logo / Title */}
      <div className="p-6 border-b border-gray-200 flex items-center justify-between">
        {!isCollapsed && (
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              Migration Wizard
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              ThoughtSpot to Power BI
            </p>
          </div>
        )}

        <button
          onClick={toggleCollapse}
          className={`p-2 hover:bg-gray-100 rounded-lg transition-colors ${isCollapsed ? 'mx-auto' : ''
            }`}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? (
            <ChevronRight className="w-5 h-5 text-gray-600" />
          ) : (
            <ChevronLeft className="w-5 h-5 text-gray-600" />
          )}
        </button>
      </div>

      {/* Steps */}
      <nav className="flex-1 p-4">
        <div className="space-y-2">
          {MIGRATION_STEPS.map((step) => {
            const Icon = step.icon;
            const isActive = step.id === currentStep;
            const isCompleted = step.id < currentStep;

            return (
              <div
                key={step.id}
                onClick={() => handleStepClick(step)}
                className={`flex items-center gap-3 p-3 rounded-lg transition-colors cursor-pointer ${isActive
                    ? 'bg-blue-50 border-l-4 border-blue-600'
                    : 'hover:bg-gray-50'
                  }`}
                title={isCollapsed ? step.name : ''}
              >
                <div
                  className={`flex-shrink-0 ${isActive
                      ? 'text-blue-600'
                      : isCompleted
                        ? 'text-green-600'
                        : 'text-gray-400'
                    }`}
                >
                  {isCompleted ? (
                    <CheckCircle className="w-5 h-5" />
                  ) : (
                    <Icon className="w-5 h-5" />
                  )}
                </div>

                {!isCollapsed && (
                  <div className="flex-1">
                    <div
                      className={`text-sm font-medium ${isActive ? 'text-blue-900' : 'text-gray-700'
                        }`}
                    >
                      {step.name}
                    </div>
                    <div className="text-xs text-gray-500">
                      Step {step.id} of 5
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      {!isCollapsed && (
        <div className="p-4 border-t border-gray-200">
          <div className="text-xs text-gray-500 text-center">
            Progress: {currentStep}/5
          </div>
        </div>
      )}
    </div>
  );
}