/**
 * Migration Stats Cards - Display key metrics
 */
import { FileText, CheckCircle, AlertCircle, TrendingUp } from 'lucide-react';
import Card from '../common/Card';

export default function MigrationStatsCards({ migration, stats }) {
  const cards = [
    {
      title: 'Total Conversions',
      value: stats.total,
      icon: FileText,
      color: 'blue',
      bgColor: 'bg-blue-100',
      textColor: 'text-blue-600',
    },
    {
      title: 'Validated',
      value: stats.validated,
      icon: CheckCircle,
      color: 'green',
      bgColor: 'bg-green-100',
      textColor: 'text-green-600',
      subtitle: `${stats.passRate.toFixed(1)}% pass rate`,
    },
    {
      title: 'Pending Review',
      value: stats.pending + stats.failed,
      icon: AlertCircle,
      color: stats.failed > 0 ? 'red' : 'yellow',
      bgColor: stats.failed > 0 ? 'bg-red-100' : 'bg-yellow-100',
      textColor: stats.failed > 0 ? 'text-red-600' : 'text-yellow-600',
      subtitle: stats.failed > 0 ? `${stats.failed} failed` : 'In progress',
    },
    {
      title: 'Avg Confidence',
      value: `${stats.avgConfidence.toFixed(1)}%`,
      icon: TrendingUp,
      color: 'purple',
      bgColor: 'bg-purple-100',
      textColor: 'text-purple-600',
      subtitle: 'AI confidence score',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, index) => (
        <Card key={index} className="p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">{card.title}</p>
              <p className="text-3xl font-bold text-gray-900 mb-1">
                {card.value}
              </p>
              {card.subtitle && (
                <p className="text-sm text-gray-500">{card.subtitle}</p>
              )}
            </div>

            <div className={`w-12 h-12 ${card.bgColor} rounded-lg flex items-center justify-center`}>
              <card.icon className={`w-6 h-6 ${card.textColor}`} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
