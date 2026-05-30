import { Database, Columns, AlertTriangle } from 'lucide-react';

const CompactStatsBar = ({ currentFile }) => {
  const totalDuplicates = currentFile?.duplicate_groups?.length || 0;

  const stats = [
    {
      label: 'Rows',
      value: currentFile?.row_count?.toLocaleString() || '0',
      icon: Database,
      color: 'blue'
    },
    {
      label: 'Columns',
      value: currentFile?.column_count || '0',
      icon: Columns,
      color: 'purple'
    },
    {
      label: 'Issues',
      value: totalDuplicates,
      icon: AlertTriangle,
      color: totalDuplicates > 0 ? 'amber' : 'emerald'
    }
  ];

  const colorClasses = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200'
  };

  const iconColors = {
    blue: 'text-blue-600',
    purple: 'text-purple-600',
    amber: 'text-amber-600',
    emerald: 'text-emerald-600'
  };

  return (
    <div className="flex items-center gap-2">
      {stats.map((stat, index) => (
        <div
          key={index}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border shadow-md ${colorClasses[stat.color]}`}
        >
          <stat.icon className={`w-3.5 h-3.5 ${iconColors[stat.color]}`} />
          <div className="flex items-baseline gap-1">
            <span className="text-sm font-bold">{stat.value}</span>
            <span className="text-[10px] font-medium opacity-75">{stat.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default CompactStatsBar;
