/**
 * Migration Export Page - Generate and download Power BI artifacts
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Download,
    FileText,
    CheckCircle,
    AlertCircle,
    ArrowLeft,
} from 'lucide-react';
import toast from 'react-hot-toast';

import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Spinner from '../components/common/Spinner';
import migrationApi from '../services/migrationApi';
import useMigrationStore from '../stores/migrationStore';

export default function MigrationExportPage() {
    const { migrationId } = useParams();
    const navigate = useNavigate();

    const { actions, currentMigration } = useMigrationStore();

    const [isLoading, setIsLoading] = useState(true);
    const [isGenerating, setIsGenerating] = useState(false);
    const [exportReady, setExportReady] = useState(false);
    const [error, setError] = useState(null);

    const loadMigrationStatus = useCallback(async () => {
        if (!migrationId) {
            setError('Migration ID is missing.');
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const migration = await migrationApi.getMigrationStatus(migrationId);
            actions.setMigration(migration);

            if (migration?.status !== 'completed') {
                setError('Migration must be completed before exporting artifacts.');
            }
        } catch (err) {
            console.error('Failed to load migration:', err);
            setError('Failed to load migration details.');
        } finally {
            setIsLoading(false);
        }
    }, [migrationId, actions]);

    useEffect(() => {
        loadMigrationStatus();
    }, [loadMigrationStatus]);

    const handleGenerateExport = async () => {
        if (!migrationId) {
            toast.error('Migration ID is missing.');
            return;
        }

        setIsGenerating(true);
        setError(null);

        try {
            await migrationApi.exportPowerBI(migrationId);

            setExportReady(true);
            toast.success('Power BI artifacts ready for download!');
        } catch (err) {
            console.error('Export generation failed:', err);
            setError('Failed to generate Power BI artifacts. Please try again.');
            toast.error('Export generation failed');
        } finally {
            setIsGenerating(false);
        }
    };

    const handleDownload = async () => {
        if (!migrationId) {
            toast.error('Migration ID is missing.');
            return;
        }

        try {
            const blob = await migrationApi.downloadArtifacts(migrationId);

            const url = window.URL.createObjectURL(new Blob([blob]));
            const link = document.createElement('a');

            const timestamp = new Date()
                .toISOString()
                .replace(/[:.]/g, '-')
                .slice(0, 19);

            link.href = url;
            link.setAttribute(
                'download',
                `thoughtspot_powerbi_migration_${migrationId}_${timestamp}.zip`
            );

            document.body.appendChild(link);
            link.click();
            link.remove();

            window.URL.revokeObjectURL(url);

            toast.success('Download started');
        } catch (err) {
            console.error('Download failed:', err);
            toast.error('Failed to download artifacts');
        }
    };

    if (isLoading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <Spinner size="xl" />
            </div>
        );
    }

    const migrationStatus = currentMigration?.status || 'unknown';
    const isCompleted = migrationStatus === 'completed';

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="container mx-auto px-4 max-w-4xl">
                <div className="mb-6">
                    <Button
                        variant="ghost"
                        onClick={() => navigate(`/migration/${migrationId}/workspace`)}
                        className="pl-0 hover:bg-transparent text-gray-600 hover:text-gray-900"
                    >
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back to Workspace
                    </Button>
                </div>

                <div className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-900">
                        Export Artifacts
                    </h1>

                    <p className="text-gray-600 mt-2">
                        Generate and download your converted Power BI project files.
                    </p>
                </div>

                {error && (
                    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                        <p className="text-red-800">{error}</p>
                    </div>
                )}

                {/* Status Card */}
                <Card className="mb-6 p-6">
                    <div className="flex items-center gap-4">
                        <div
                            className={`w-12 h-12 rounded-full flex items-center justify-center ${isCompleted ? 'bg-green-100' : 'bg-gray-100'
                                }`}
                        >
                            {isCompleted ? (
                                <CheckCircle className="w-6 h-6 text-green-600" />
                            ) : (
                                <FileText className="w-6 h-6 text-gray-400" />
                            )}
                        </div>

                        <div>
                            <h3 className="text-lg font-semibold text-gray-900">
                                Migration Status:{' '}
                                <span className="capitalize">{migrationStatus}</span>
                            </h3>

                            <p className="text-sm text-gray-600">
                                {isCompleted
                                    ? 'All calculations converted and validated. Ready for export.'
                                    : 'Migration must be completed before exporting.'}
                            </p>
                        </div>
                    </div>
                </Card>

                {/* Export Actions */}
                <Card className="p-8 text-center">
                    <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-6">
                        <Download className="w-8 h-8 text-blue-600" />
                    </div>

                    <h2 className="text-xl font-semibold text-gray-900 mb-2">
                        Power BI Project Files
                    </h2>

                    <p className="text-gray-600 mb-8 max-w-md mx-auto">
                        This will generate a ZIP file containing the Power BI project
                        structure, semantic model, DAX measures, and migration artifacts.
                    </p>

                    <div className="flex flex-col items-center gap-4">
                        {!exportReady ? (
                            <Button
                                size="lg"
                                onClick={handleGenerateExport}
                                disabled={isGenerating || !isCompleted}
                                className="min-w-[200px]"
                            >
                                {isGenerating ? (
                                    <>
                                        <Spinner size="sm" className="mr-2 text-white" />
                                        Generating...
                                    </>
                                ) : (
                                    'Generate Export'
                                )}
                            </Button>
                        ) : (
                            <div className="w-full max-w-md space-y-4">
                                <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-800 text-sm flex items-center justify-center gap-2">
                                    <CheckCircle className="w-4 h-4" />
                                    Export generated successfully!
                                </div>

                                <div className="flex flex-col gap-3">
                                    <Button
                                        size="lg"
                                        onClick={handleDownload}
                                        className="w-full gap-2 justify-center"
                                    >
                                        <Download className="w-5 h-5" />
                                        Download ZIP
                                    </Button>

                                    <Button
                                        variant="ghost"
                                        onClick={() => setExportReady(false)}
                                        className="text-gray-500 hover:text-gray-700 w-full"
                                    >
                                        Regenerate Export
                                    </Button>
                                </div>
                            </div>
                        )}
                    </div>
                </Card>

                {/* Included Items */}
                <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Card className="p-4">
                        <h3 className="font-semibold text-gray-900 mb-2">
                            Semantic Model
                        </h3>

                        <p className="text-sm text-gray-500">
                            Complete data model with relationships, calculated columns, and
                            measures.
                        </p>
                    </Card>

                    <Card className="p-4">
                        <h3 className="font-semibold text-gray-900 mb-2">
                            DAX Measures
                        </h3>

                        <p className="text-sm text-gray-500">
                            All converted ThoughtSpot calculations optimized for Power BI.
                        </p>
                    </Card>

                    <Card className="p-4">
                        <h3 className="font-semibold text-gray-900 mb-2">
                            Project Structure
                        </h3>

                        <p className="text-sm text-gray-500">
                            Standard Power BI project structure ready for Power BI Desktop.
                        </p>
                    </Card>
                </div>
            </div>
        </div>
    );
}