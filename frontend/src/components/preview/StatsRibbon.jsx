import { Database, Columns, AlertTriangle } from 'lucide-react';

const StatsRibbon = ({ currentFile }) => {
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
      color: 'blue',
      bgColor: 'bg-blue-50',
      iconColor: 'text-blue-600',
      textColor: 'text-blue-900'
    },
    {
      label: 'Total Columns',
      value: currentFile?.column_count || '0',
      icon: Columns,
      color: 'purple',
      bgColor: 'bg-purple-50',
      iconColor: 'text-purple-600',
      textColor: 'text-purple-900'
    },
    {
      label: 'Issues Found',
      value: totalDuplicates,
      sublabel: duplicateColumns > 0 ? `${duplicateColumns} duplicate columns` : 'No issues',
      icon: AlertTriangle,
      color: totalDuplicates > 0 ? 'amber' : 'emerald',
      bgColor: totalDuplicates > 0 ? 'bg-amber-50' : 'bg-emerald-50',
      iconColor: totalDuplicates > 0 ? 'text-amber-600' : 'text-emerald-600',
      textColor: totalDuplicates > 0 ? 'text-amber-900' : 'text-emerald-900'
    }
  ];

  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      {stats.map((stat, index) => (
        <div
          key={index}
          className={`${stat.bgColor} rounded-xl p-5 border-2 border-transparent hover:border-${stat.color}-200 transition-all duration-200`}
        >
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-lg bg-white shadow-sm`}>
              <stat.icon className={`w-5 h-5 ${stat.iconColor}`} />
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">
                {stat.label}
              </p>
              <p className={`text-2xl font-bold ${stat.textColor} mt-0.5`}>
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

export default StatsRibbon;
