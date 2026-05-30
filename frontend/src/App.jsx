import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';

import Spinner from './components/common/Spinner.jsx';
import ErrorBoundary from './components/common/ErrorBoundary.jsx';

// Lazy load pages for code splitting
const HomePage = lazy(() => import('./pages/HomePage.jsx'));
const UploadPage = lazy(() => import('./pages/UploadPage.jsx'));
const PreviewPage = lazy(() => import('./pages/PreviewPage.jsx'));
const ProcessingPage = lazy(() => import('./pages/ProcessingPage.jsx'));
const ResultsPage = lazy(() => import('./pages/ResultsPage.jsx'));

// ThoughtSpot -> Power BI migration pages
const MigrationUploadPage = lazy(() => import('./pages/MigrationUploadPage.jsx'));
const MigrationWorkspacePage = lazy(() => import('./pages/MigrationWorkspacePage.jsx'));
const MigrationExportPage = lazy(() => import('./pages/MigrationExportPage.jsx'));

// 5-Page ThoughtSpot -> Power BI Migration Wizard
const Page1DataUnderstanding = lazy(() =>
  import('./pages/migration-wizard/Page1DataUnderstanding.jsx')
);

const Page2ModelIntelligence = lazy(() =>
  import('./pages/migration-wizard/Page2ModelIntelligence.jsx')
);

// Correct file name based on your folder screenshot
const Page3FieldMapping = lazy(() =>
  import('./pages/migration-wizard/Page3FieldMapping.jsx')
);

const Page4DAXConversion = lazy(() =>
  import('./pages/migration-wizard/Page4DAXConversion.jsx')
);

const Page5Recommendations = lazy(() =>
  import('./pages/migration-wizard/Page5Recommendations.jsx')
);

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#fff',
              color: '#111827',
              borderRadius: '8px',
              boxShadow:
                '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
            },
            success: {
              iconTheme: {
                primary: '#10b981',
                secondary: '#fff',
              },
            },
            error: {
              iconTheme: {
                primary: '#ef4444',
                secondary: '#fff',
              },
            },
          }}
        />

        <Suspense
          fallback={
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
              <Spinner size="xl" />
            </div>
          }
        >
          <Routes>
            {/* Home */}
            <Route path="/" element={<HomePage />} />

            {/* ThoughtSpot metadata analysis routes */}
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/jobs/:previewId/preview" element={<PreviewPage />} />
            <Route path="/jobs/:jobId/processing" element={<ProcessingPage />} />
            <Route path="/jobs/:jobId/results" element={<ResultsPage />} />

            {/* ThoughtSpot -> Power BI migration routes */}
            <Route path="/migration" element={<MigrationUploadPage />} />
            <Route
              path="/migration/:migrationId/workspace"
              element={<MigrationWorkspacePage />}
            />
            <Route
              path="/migration/:migrationId/export"
              element={<MigrationExportPage />}
            />

            {/* ThoughtSpot -> Power BI migration wizard */}
            <Route
              path="/migration-wizard"
              element={<Navigate to="/migration-wizard/data-understanding" replace />}
            />

            <Route
              path="/migration-wizard/data-understanding"
              element={<Page1DataUnderstanding />}
            />

            <Route
              path="/migration-wizard/model-intelligence"
              element={<Page2ModelIntelligence />}
            />

            <Route
              path="/migration-wizard/field-mapping"
              element={<Page3FieldMapping />}
            />

            <Route
              path="/migration-wizard/formula-conversion"
              element={<Page4DAXConversion />}
            />

            <Route
              path="/migration-wizard/review"
              element={<Page5Recommendations />}
            />

            {/* Optional aliases for old paths */}
            <Route
              path="/migration-wizard/tableau-logic"
              element={<Navigate to="/migration-wizard/field-mapping" replace />}
            />

            <Route
              path="/migration-wizard/thoughtspot-logic"
              element={<Navigate to="/migration-wizard/field-mapping" replace />}
            />

            <Route
              path="/migration-wizard/visualization-mapping"
              element={<Navigate to="/migration-wizard/formula-conversion" replace />}
            />

            <Route
              path="/migration-wizard/validation"
              element={<Navigate to="/migration-wizard/review" replace />}
            />

            <Route
              path="/migration-wizard/recommendations"
              element={<Navigate to="/migration-wizard/review" replace />}
            />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;