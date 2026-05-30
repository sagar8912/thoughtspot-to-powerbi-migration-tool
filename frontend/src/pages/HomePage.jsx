/**
 * Home Page - Choose between ThoughtSpot Metadata Analysis or ThoughtSpot to Power BI Migration
 */
import { useNavigate } from 'react-router-dom';
import { FileSpreadsheet, GitBranch, ArrowRight } from 'lucide-react';
import Card from '../components/common/Card';
import Button from '../components/common/Button';

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="container mx-auto px-4 py-16 max-w-6xl">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            AI-Powered ThoughtSpot to Power BI Migration
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Choose your workflow: Analyze ThoughtSpot metadata or migrate worksheets, answers,
            liveboards, formulas, and relationships to Power BI
          </p>
        </div>

        {/* Two Options */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl mx-auto">
          {/* ThoughtSpot Metadata Analysis */}
          <Card className="p-8 hover:shadow-xl transition-shadow cursor-pointer group">
            <div className="w-16 h-16 bg-green-100 rounded-lg flex items-center justify-center mb-6 group-hover:bg-green-200 transition-colors">
              <FileSpreadsheet className="w-8 h-8 text-green-600" />
            </div>

            <h2 className="text-2xl font-bold text-gray-900 mb-3">
              ThoughtSpot Metadata Analysis
            </h2>

            <p className="text-gray-600 mb-6">
              Upload ThoughtSpot TML, YAML, JSON, ZIP, CSV, or Excel files and let AI analyze
              objects, formulas, relationships, and dependencies before migration.
            </p>

            <ul className="space-y-2 mb-8 text-sm text-gray-700">
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-0.5">✓</span>
                <span>Automatic ThoughtSpot object detection</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-0.5">✓</span>
                <span>Visual graph of metadata relationships</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 mt-0.5">✓</span>
                <span>Export migration-ready analysis report</span>
              </li>
            </ul>

            <Button
              onClick={() => navigate('/upload')}
              className="w-full gap-2 group-hover:bg-green-700"
            >
              Start Metadata Analysis
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Card>

          {/* ThoughtSpot to Power BI Migration */}
          <Card className="p-8 hover:shadow-xl transition-shadow cursor-pointer group border-2 border-blue-500">
            <div className="w-16 h-16 bg-blue-100 rounded-lg flex items-center justify-center mb-6 group-hover:bg-blue-200 transition-colors">
              <GitBranch className="w-8 h-8 text-blue-600" />
            </div>

            <h2 className="text-2xl font-bold text-gray-900 mb-3">
              ThoughtSpot → Power BI Migration
            </h2>

            <p className="text-gray-600 mb-6">
              Migrate ThoughtSpot worksheets, answers, liveboards, formulas, and relationships
              to Power BI-compatible outputs with DAX conversion and validation.
            </p>

            <ul className="space-y-2 mb-8 text-sm text-gray-700">
              <li className="flex items-start gap-2">
                <span className="text-blue-600 mt-0.5">✓</span>
                <span>ThoughtSpot formula to DAX conversion</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-600 mt-0.5">✓</span>
                <span>Automated validation and migration checks</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-600 mt-0.5">✓</span>
                <span>Export Power BI-compatible migration outputs</span>
              </li>
            </ul>

            <Button
              onClick={() => navigate('/migration')}
              className="w-full gap-2 bg-blue-600 hover:bg-blue-700"
            >
              Start ThoughtSpot Migration
              <ArrowRight className="w-4 h-4" />
            </Button>

            <div className="mt-4 px-3 py-2 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-800 font-medium">
                ⭐ ThoughtSpot to Power BI - Powered by AI
              </p>
            </div>
          </Card>
        </div>

        {/* Footer Info */}
        <div className="text-center mt-12 text-sm text-gray-500">
          <p>Both workflows use advanced AI to understand your BI metadata and automate migration tasks</p>
        </div>
      </div>
    </div>
  );
}