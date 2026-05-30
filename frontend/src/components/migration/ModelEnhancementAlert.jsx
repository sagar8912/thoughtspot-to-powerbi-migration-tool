/**
 * Model Enhancement Alert - Shows when table calculations require Power BI model changes
 */
import React, { useState, useEffect } from 'react';
import { AlertCircle, Download, FileText, ExternalLink } from 'lucide-react';
import Button from '../common/Button';
import Card from '../common/Card';
import migrationApi from '../../services/migrationApi';
import toast from 'react-hot-toast';

export default function ModelEnhancementAlert({ migrationId }) {
  const [hasEnhancements, setHasEnhancements] = useState(false);
  const [enhancementInfo, setEnhancementInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkEnhancements();
  }, [migrationId]);

  const checkEnhancements = async () => {
    try {
      const response = await migrationApi.getModelEnhancements(migrationId);
      setHasEnhancements(response.has_enhancements);
      setEnhancementInfo(response);
    } catch (error) {
      console.error('Failed to check model enhancements:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadGuide = async () => {
    try {
      await migrationApi.downloadEnhancementGuide(migrationId);
      toast.success('Enhancement guide downloaded');
    } catch (error) {
      toast.error('Failed to download guide');
    }
  };

  const handleDownloadAll = async () => {
    try {
      await migrationApi.downloadAllEnhancements(migrationId);
      toast.success('All enhancement files downloaded');
    } catch (error) {
      toast.error('Failed to download files');
    }
  };

  if (isLoading) return null;
  if (!hasEnhancements) return null;

  return (
    <Card className="border-orange-200 bg-orange-50">
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className="flex-shrink-0">
          <AlertCircle className="w-6 h-6 text-orange-600" />
        </div>

        {/* Content */}
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-orange-900 mb-2">
            ⚙️ Model Enhancements Required
          </h3>
          <p className="text-sm text-orange-800 mb-4">
            Some calculations use <strong>Tableau Table Calculations</strong> (LOOKUP, INDEX, RUNNING_SUM, etc.)
            that require changes to your Power BI data model. These cannot be converted to DAX measures alone.
          </p>

          {/* Stats */}
          {enhancementInfo && (
            <div className="bg-white rounded-lg border border-orange-200 p-3 mb-4">
              <div className="text-sm text-gray-600">
                <strong>{enhancementInfo.enhancement_count || 'Several'}</strong> calculation(s) need model changes:
              </div>
              <ul className="mt-2 space-y-1 text-sm text-gray-700">
                <li>✅ We've generated Power Query M code</li>
                <li>✅ We've generated DAX calculated columns</li>
                <li>✅ We've provided step-by-step instructions</li>
              </ul>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              onClick={handleDownloadGuide}
              variant="primary"
              size="sm"
              icon={FileText}
            >
              Download Enhancement Guide
            </Button>
            <Button
              onClick={handleDownloadAll}
              variant="secondary"
              size="sm"
              icon={Download}
            >
              Download All Files (ZIP)
            </Button>
          </div>

          {/* Info */}
          <div className="mt-3 text-xs text-orange-700">
            <ExternalLink className="inline w-3 h-3 mr-1" />
            You'll need to manually apply these changes in Power BI Desktop before the migration is complete.
          </div>
        </div>
      </div>
    </Card>
  );
}
