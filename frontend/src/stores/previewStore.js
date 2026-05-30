import { create } from 'zustand';

/**
 * Preview store for managing file preview and duplicate column detection state
 */
const usePreviewStore = create((set, get) => ({
  // State
  previewId: null,
  previewData: null,
  fileSelections: {}, // { file_id: { columns_to_delete: [...] } }
  isLoading: false,
  error: null,
  selectedFileIndex: 0,

  // Actions
  setPreviewData: (data) => {
    // Initialize file selections with recommendations
    const fileSelections = {};

    if (data && data.files) {
      data.files.forEach(file => {
        const columnsToDelete = [];

        // Auto-select columns based on recommendations
        file.duplicate_groups?.forEach(group => {
          // Parse recommendation to determine which columns to delete
          // Keep first column, mark others for deletion if content is identical
          if (group.columns && group.columns.length > 1) {
            // Check if metadata indicates identical content
            const contentIdentical = group.metadata?.content_identical || [];

            // Delete columns that are identical to the first column
            group.columns.slice(1).forEach((col, index) => {
              if (contentIdentical[index + 1]) {
                columnsToDelete.push(col);
              }
            });
          }
        });

        fileSelections[file.file_id] = {
          columns_to_delete: columnsToDelete
        };
      });
    }

    set({
      previewId: data?.preview_id || null,
      previewData: data,
      fileSelections,
      error: null
    });
  },

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error, isLoading: false }),

  setSelectedFileIndex: (index) => set({ selectedFileIndex: index }),

  toggleColumnDeletion: (fileId, columnName) => {
    const { fileSelections } = get();
    const currentSelections = fileSelections[fileId] || { columns_to_delete: [] };
    const columnsToDelete = [...currentSelections.columns_to_delete];

    const index = columnsToDelete.indexOf(columnName);
    if (index > -1) {
      // Remove from deletion list
      columnsToDelete.splice(index, 1);
    } else {
      // Add to deletion list
      columnsToDelete.push(columnName);
    }

    set({
      fileSelections: {
        ...fileSelections,
        [fileId]: {
          columns_to_delete: columnsToDelete
        }
      }
    });
  },

  selectAllRecommended: () => {
    const { previewData } = get();
    if (!previewData?.files) return;

    const fileSelections = {};
    previewData.files.forEach(file => {
      const columnsToDelete = [];

      file.duplicate_groups?.forEach(group => {
        const contentIdentical = group.metadata?.content_identical || [];
        group.columns.slice(1).forEach((col, index) => {
          if (contentIdentical[index + 1]) {
            columnsToDelete.push(col);
          }
        });
      });

      fileSelections[file.file_id] = { columns_to_delete: columnsToDelete };
    });

    set({ fileSelections });
  },

  clearSelections: () => {
    const { previewData } = get();
    if (!previewData?.files) return;

    const fileSelections = {};
    previewData.files.forEach(file => {
      fileSelections[file.file_id] = { columns_to_delete: [] };
    });

    set({ fileSelections });
  },

  getConfirmPayload: () => {
    const { fileSelections } = get();
    return {
      file_selections: Object.keys(fileSelections).map(fileId => ({
        file_id: fileId,
        columns_to_delete: fileSelections[fileId].columns_to_delete
      }))
    };
  },

  getTotalColumnsToDelete: () => {
    const { fileSelections } = get();
    return Object.values(fileSelections).reduce(
      (total, selection) => total + selection.columns_to_delete.length,
      0
    );
  },

  isColumnMarkedForDeletion: (fileId, columnName) => {
    const { fileSelections } = get();
    const selection = fileSelections[fileId];
    return selection?.columns_to_delete?.includes(columnName) || false;
  },

  reset: () => set({
    previewId: null,
    previewData: null,
    fileSelections: {},
    isLoading: false,
    error: null,
    selectedFileIndex: 0
  })
}));

export default usePreviewStore;
