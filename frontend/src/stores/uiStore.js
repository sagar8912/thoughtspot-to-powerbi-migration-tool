import { create } from 'zustand';
import toast from 'react-hot-toast';

export const useUIStore = create((set) => ({
  // UI state
  isModalOpen: false,
  activeView: 'upload',
  wsConnected: false,

  // Actions
  actions: {
    openModal: () => set({ isModalOpen: true }),

    closeModal: () => set({ isModalOpen: false }),

    setView: (view) => set({ activeView: view }),

    setWsConnected: (connected) => set({ wsConnected: connected }),

    showToast: (message, type = 'default') => {
      switch (type) {
        case 'success':
          toast.success(message);
          break;
        case 'error':
          toast.error(message);
          break;
        case 'warning':
          toast(message, {
            icon: '⚠️',
          });
          break;
        default:
          toast(message);
      }
    }
  }
}));
