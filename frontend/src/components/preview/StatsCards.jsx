import { Database, Columns, AlertTriangle } from 'lucide-react';

const StatsCards = ({ currentFile }) => {
  const totalDuplicates = currentFile?.duplicate_groups?.length || 0;
  const duplicateColumns = currentFile?.duplicate_groups?.reduce(
    (sum, group) => sum + group.columns.length,
    0
  ) || 0;

  const stats = [
    {
      label: 'Total Rows',
      value: currentFile?.row_count?.toLocaleString() || '0',
      icon: Database,
      iconColor: 'text-blue-600',
      iconBg: 'bg-blue-50'
    },
    {
      label: 'Total Columns',
      value: currentFile?.column_count || '0',
      icon: Columns,
      iconColor: 'text-purple-600',
      iconBg: 'bg-purple-50'
    },
    {
      label: 'Issues Found',
      value: totalDuplicates,
      sublabel: duplicateColumns > 0 ? `${duplicateColumns} duplicate columns` : 'No issues',
      icon: AlertTriangle,
      iconColor: totalDuplicates > 0 ? 'text-amber-600' : 'text-emerald-600',
      iconBg: totalDuplicates > 0 ? 'bg-amber-50' : 'bg-emerald-50'
    }
  ];

  return (
    <div className="grid grid-cols-3 gap-4">
      {stats.map((stat, index) => (
        <div
          key={index}
          className="bg-white rounded-lg p-5 border border-slate-200 shadow-sm"
        >
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-lg ${stat.iconBg}`}>
              <stat.icon className={`w-6 h-6 ${stat.iconColor}`} />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-600">
                {stat.label}
              </p>
              <p className="text-3xl font-bold text-black mt-1">
                {stat.value}
              </p>
              {stat.sublabel && (
                <p className="text-xs text-gray-500 mt-1">{stat.sublabel}</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default StatsCards;
