/**
 * Migration Store - Zustand store for ThoughtSpot to Power BI migration state
 */
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

const initialState = {
  currentMigration: null,

  workbooks: [],
  calculations: [],
  conversions: [],
  validationResults: [],

  fidelityValidation: null,
  correctionHistory: [],

  logicGraph: {
    nodes: [],
    edges: [],
    stats: {},
  },

  selectedCalculation: null,
  selectedConversion: null,
  isValidating: false,
  isExporting: false,

  conversionStatusFilter: 'all',
  confidenceFilter: 'all',
};

const useMigrationStore = create(
  devtools(
    (set, get) => ({
      ...initialState,

      actions: {
        setMigration: (migration) =>
          set({ currentMigration: migration }, false, 'setMigration'),

        updateMigrationStatus: (status) =>
          set(
            (state) => ({
              currentMigration: state.currentMigration
                ? {
                  ...state.currentMigration,
                  status,
                }
                : null,
            }),
            false,
            'updateMigrationStatus'
          ),

        updateMigrationProgress: (progress_percent, current_stage) =>
          set(
            (state) => ({
              currentMigration: state.currentMigration
                ? {
                  ...state.currentMigration,
                  progress_percent,
                  current_stage,
                }
                : null,
            }),
            false,
            'updateMigrationProgress'
          ),

        setWorkbooks: (workbooks) =>
          set(
            { workbooks: Array.isArray(workbooks) ? workbooks : [] },
            false,
            'setWorkbooks'
          ),

        setCalculations: (calculations) =>
          set(
            { calculations: Array.isArray(calculations) ? calculations : [] },
            false,
            'setCalculations'
          ),

        selectCalculation: (calcId) =>
          set({ selectedCalculation: calcId }, false, 'selectCalculation'),

        setConversions: (conversions) =>
          set(
            { conversions: Array.isArray(conversions) ? conversions : [] },
            false,
            'setConversions'
          ),

        selectConversion: (conversionId) =>
          set({ selectedConversion: conversionId }, false, 'selectConversion'),

        updateConversion: (conversionId, updates) =>
          set(
            (state) => ({
              conversions: state.conversions.map((conversion) =>
                conversion.conversion_id === conversionId
                  ? { ...conversion, ...updates }
                  : conversion
              ),
            }),
            false,
            'updateConversion'
          ),

        setLogicGraph: (logicGraph) =>
          set(
            {
              logicGraph: {
                nodes: Array.isArray(logicGraph?.nodes)
                  ? logicGraph.nodes
                  : [],
                edges: Array.isArray(logicGraph?.edges)
                  ? logicGraph.edges
                  : [],
                stats: logicGraph?.stats || {},
              },
            },
            false,
            'setLogicGraph'
          ),

        setValidationResults: (validationResults) =>
          set(
            {
              validationResults: Array.isArray(validationResults)
                ? validationResults
                : [],
            },
            false,
            'setValidationResults'
          ),

        setFidelityValidation: (fidelityValidation) =>
          set({ fidelityValidation }, false, 'setFidelityValidation'),

        setCorrectionHistory: (correctionHistory) =>
          set(
            {
              correctionHistory: Array.isArray(correctionHistory)
                ? correctionHistory
                : [],
            },
            false,
            'setCorrectionHistory'
          ),

        addCorrectionAttempt: (attempt) =>
          set(
            (state) => ({
              correctionHistory: [...state.correctionHistory, attempt],
            }),
            false,
            'addCorrectionAttempt'
          ),

        setIsValidating: (isValidating) =>
          set({ isValidating }, false, 'setIsValidating'),

        setIsExporting: (isExporting) =>
          set({ isExporting }, false, 'setIsExporting'),

        setConversionStatusFilter: (filter) =>
          set(
            { conversionStatusFilter: filter },
            false,
            'setConversionStatusFilter'
          ),

        setConfidenceFilter: (filter) =>
          set({ confidenceFilter: filter }, false, 'setConfidenceFilter'),

        clearMigration: () => set({ ...initialState }, false, 'clearMigration'),
      },

      selectors: {
        getSelectedCalculation: () => {
          const state = get();

          return state.calculations.find(
            (calculation) =>
              calculation.calc_id === state.selectedCalculation ||
              calculation.id === state.selectedCalculation
          );
        },

        getSelectedConversion: () => {
          const state = get();

          return state.conversions.find(
            (conversion) =>
              conversion.conversion_id === state.selectedConversion ||
              conversion.id === state.selectedConversion
          );
        },

        getFilteredConversions: () => {
          const state = get();

          let filtered = Array.isArray(state.conversions)
            ? [...state.conversions]
            : [];

          if (state.conversionStatusFilter !== 'all') {
            filtered = filtered.filter(
              (conversion) =>
                conversion.status === state.conversionStatusFilter
            );
          }

          if (state.confidenceFilter === 'high') {
            filtered = filtered.filter(
              (conversion) => (conversion.confidence_score || 0) >= 0.9
            );
          } else if (state.confidenceFilter === 'medium') {
            filtered = filtered.filter((conversion) => {
              const score = conversion.confidence_score || 0;
              return score >= 0.7 && score < 0.9;
            });
          } else if (state.confidenceFilter === 'low') {
            filtered = filtered.filter(
              (conversion) => (conversion.confidence_score || 0) < 0.7
            );
          }

          return filtered;
        },

        getConversionStats: () => {
          const state = get();
          const conversions = Array.isArray(state.conversions)
            ? state.conversions
            : [];

          const total = conversions.length;

          if (total === 0) {
            return {
              total: 0,
              validated: 0,
              pending: 0,
              failed: 0,
              passRate: 0,
              avgConfidence: 0,
            };
          }

          const validated = conversions.filter(
            (conversion) => conversion.status === 'validated'
          ).length;

          const pending = conversions.filter(
            (conversion) => conversion.status === 'pending'
          ).length;

          const failed = conversions.filter(
            (conversion) => conversion.status === 'failed'
          ).length;

          const avgConfidence =
            conversions.reduce(
              (sum, conversion) =>
                sum + (conversion.confidence_score || 0),
              0
            ) / total;

          return {
            total,
            validated,
            pending,
            failed,
            passRate: (validated / total) * 100,
            avgConfidence: avgConfidence * 100,
          };
        },

        getValidationSummary: () => {
          const state = get();
          const results = Array.isArray(state.validationResults)
            ? state.validationResults
            : [];

          if (results.length === 0) {
            return null;
          }

          const totalSlices = results.reduce(
            (sum, result) => sum + (result.test_slices?.length || 0),
            0
          );

          const passedSlices = results.reduce(
            (sum, result) =>
              sum +
              (result.test_slices?.filter((slice) => slice.passed).length ||
                0),
            0
          );

          return {
            totalConversions: results.length,
            totalSlices,
            passedSlices,
            failedSlices: totalSlices - passedSlices,
            passRate:
              totalSlices > 0 ? (passedSlices / totalSlices) * 100 : 0,
          };
        },

        getFidelityMetrics: () => {
          const state = get();
          const fidelity = state.fidelityValidation;

          if (!fidelity) {
            return {
              isAvailable: false,
              passRate: 0,
              totalSlices: 0,
              passedSlices: 0,
              failedSlices: 0,
              correctionAttempts: 0,
              errorBreakdown: {},
            };
          }

          const testSlices = Array.isArray(fidelity.test_slices)
            ? fidelity.test_slices
            : [];

          const totalSlices = testSlices.length;
          const passedSlices = testSlices.filter(
            (slice) => slice.passed
          ).length;
          const failedSlices = totalSlices - passedSlices;

          const errorBreakdown = {};

          testSlices.forEach((slice) => {
            if (!slice.passed) {
              const category = slice.error_category || 'unknown';
              errorBreakdown[category] =
                (errorBreakdown[category] || 0) + 1;
            }
          });

          return {
            isAvailable: true,
            passRate: (fidelity.pass_rate || 0) * 100,
            totalSlices,
            passedSlices,
            failedSlices,
            correctionAttempts: fidelity.correction_attempts || 0,
            errorBreakdown,
            overallPassed: Boolean(fidelity.overall_passed),
          };
        },

        getCorrectionSummary: () => {
          const state = get();
          const history = Array.isArray(state.correctionHistory)
            ? state.correctionHistory
            : [];

          if (history.length === 0) {
            return {
              totalAttempts: 0,
              successfulCorrections: 0,
              failedCorrections: 0,
            };
          }

          const successful = history.filter(
            (attempt) => attempt.corrected_dax !== attempt.original_dax
          ).length;

          return {
            totalAttempts: history.length,
            successfulCorrections: successful,
            failedCorrections: history.length - successful,
          };
        },
      },
    }),
    { name: 'MigrationStore' }
  )
);

export default useMigrationStore;