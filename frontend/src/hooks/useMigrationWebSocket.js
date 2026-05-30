import { useEffect, useState, useRef } from 'react';
import { config } from '../config.js';
import migrationApi from '../services/migrationApi.js';

/**
 * Custom hook for migration WebSocket connections with fallback polling
 *
 * PERFORMANCE FIX #5: Adds exponential backoff for fallback polling
 * when WebSocket is unavailable
 *
 * @param {string} migrationId - The migration ID
 * @param {boolean} enabled - Whether to connect (set to false when migration is completed)
 * @returns {Object} - { lastMessage, connected }
 */
export const useMigrationWebSocket = (migrationId, enabled = true) => {
  const [lastMessage, setLastMessage] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const pollTimeoutRef = useRef(null);
  const pollIntervalRef = useRef(2000); // Start fallback polling at 2 seconds

  useEffect(() => {
    if (!migrationId || !enabled) return;

    const wsUrl = `${config.wsBaseUrl}/api/v1/migration/${migrationId}/ws`;
    console.log('Connecting to migration WebSocket:', wsUrl);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`Migration WebSocket connected for ${migrationId}`);
      setConnected(true);

      // Clear any fallback polling when WebSocket connects
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const message = {
          data: event.data,
          timestamp: new Date()
        };
        setLastMessage(message);
      } catch (error) {
        console.error('Failed to process WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('Migration WebSocket error:', error);
      setConnected(false);

      // Start fallback polling on WebSocket error
      startFallbackPolling();
    };

    ws.onclose = () => {
      console.log('Migration WebSocket closed');
      setConnected(false);

      // Start fallback polling when WebSocket closes
      startFallbackPolling();
    };

    // Fallback polling function with exponential backoff
    const startFallbackPolling = () => {
      if (pollTimeoutRef.current) return; // Already polling

      const poll = async () => {
        try {
          // Poll migration status as fallback
          const migration = await migrationApi.getMigrationStatus(migrationId);

          // Simulate WebSocket message format
          const message = {
            data: JSON.stringify({
              type: 'progress',
              migration_id: migrationId,
              progress_percent: migration.progress_percent,
              current_stage: migration.current_stage,
              status: migration.status
            }),
            timestamp: new Date()
          };
          setLastMessage(message);

          // Stop polling if completed
          if (migration.status === 'completed' || migration.status === 'failed') {
            if (pollTimeoutRef.current) {
              clearTimeout(pollTimeoutRef.current);
              pollTimeoutRef.current = null;
            }
            return;
          }

          // EXPONENTIAL BACKOFF: Gradually slow down polling
          pollIntervalRef.current = Math.min(
            pollIntervalRef.current * 1.5,
            15000  // Max 15 seconds for migration polling
          );

          // Schedule next poll
          pollTimeoutRef.current = setTimeout(poll, pollIntervalRef.current);
        } catch (error) {
          console.error('Fallback polling error:', error);

          // On error, reset to faster interval and retry
          pollIntervalRef.current = 2000;
          pollTimeoutRef.current = setTimeout(poll, pollIntervalRef.current);
        }
      };

      // Reset interval and start polling
      pollIntervalRef.current = 2000;
      poll();
    };

    return () => {
      // Cleanup WebSocket
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }

      // Cleanup polling
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
    };
  }, [migrationId, enabled]);

  return { lastMessage, connected };
};
