import { create } from 'zustand';

export const useJobStore = create((set, get) => ({
  // Current job state
  currentJob: null,
  uploadedFiles: [],
  uploadProgress: 0,

  // Actions
  actions: {
    setCurrentJob: (job) => set({ currentJob: job }),

    updateProgress: (data) => set((state) => ({
      currentJob: state.currentJob ? {
        ...state.currentJob,
        ...data
      } : data
    })),

    setResult: (result) => set((state) => ({
      currentJob: state.currentJob ? {
        ...state.currentJob,
        result,
        status: 'completed'
      } : null
    })),

    clearJob: () => set({
      currentJob: null,
      uploadedFiles: [],
      uploadProgress: 0
    }),

    setUploadedFiles: (files) => set({ uploadedFiles: files }),

    setUploadProgress: (progress) => set({ uploadProgress: progress }),

    addUploadedFile: (file) => set((state) => ({
      uploadedFiles: [...state.uploadedFiles, file]
    })),

    removeUploadedFile: (fileName) => set((state) => ({
      uploadedFiles: state.uploadedFiles.filter(f => f.name !== fileName)
    })),

    updateFileProgress: (fileName, progress) => set((state) => ({
      uploadedFiles: state.uploadedFiles.map(f =>
        f.name === fileName ? { ...f, uploadProgress: progress } : f
      )
    }))
  }
}));
