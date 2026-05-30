import { useEffect, useState } from 'react';
import { JobWebSocket } from '../services/websocket.js';
import { useJobStore } from '../stores/jobStore.js';
import { useUIStore } from '../stores/uiStore.js';

export const useWebSocket = (jobId) => {
  const [connected, setConnected] = useState(false);

  const updateProgress = useJobStore((state) => state.actions.updateProgress);
  const showToast = useUIStore((state) => state.actions.showToast);
  const setWsConnected = useUIStore((state) => state.actions.setWsConnected);

  useEffect(() => {
    if (!jobId) return;

    const handleMessage = (message) => {
      console.log('WebSocket message:', message);

      switch (message.type) {
        case 'connected':
          setConnected(true);
          setWsConnected(true);

          if (message.data) {
            updateProgress(message.data);
          }
          break;

        case 'progress':
          updateProgress(message.data);
          break;

        case 'completed':
          updateProgress({
            status: 'completed',
            progress_percent: 100,
            ...message.data,
          });

          showToast('ThoughtSpot migration completed successfully! 🎉', 'success');
          break;

        case 'error':
          updateProgress({
            status: 'failed',
            error: message.data?.error || message.data?.message || 'Job failed',
            error_message: message.data?.error || message.data?.message || 'Job failed',
          });

          showToast(
            `ThoughtSpot migration failed: ${message.data?.error || message.data?.message || 'Unknown error'
            }`,
            'error'
          );
          break;

        default:
          console.log('Unknown WebSocket message type:', message.type);
      }
    };

    const handleError = () => {
      setConnected(false);
      setWsConnected(false);
    };

    const websocket = new JobWebSocket(jobId, handleMessage, handleError);

    return () => {
      websocket.close();
      setConnected(false);
      setWsConnected(false);
    };
  }, [jobId, updateProgress, showToast, setWsConnected]);

  return { connected };
};