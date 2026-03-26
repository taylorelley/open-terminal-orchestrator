import { type ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon: ReactNode;
  trend?: { value: number; positive: boolean };
  bar?: { current: number; max: number };
}

export function StatCard({ label, value, subtitle, icon, trend, bar }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-zinc-500 truncate">{label}</p>
          <div className="mt-1 flex items-baseline gap-2">
            <p className="text-2xl font-semibold text-zinc-900">{value}</p>
            {trend && (
              <span
                className={`text-xs font-medium ${
                  trend.positive ? 'text-emerald-600' : 'text-red-600'
                }`}
              >
                {trend.positive ? '+' : ''}{trend.value}%
              </span>
            )}
          </div>
          {subtitle && <p className="mt-0.5 text-xs text-zinc-400">{subtitle}</p>}
        </div>
        <div className="flex-shrink-0 p-2.5 bg-zinc-50 rounded-lg text-zinc-600">
          {icon}
        </div>
      </div>
      {bar && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-zinc-400 mb-1">
            <span>{bar.current} / {bar.max}</span>
            <span>{Math.round((bar.current / bar.max) * 100)}%</span>
          </div>
          <div className="h-1.5 bg-zinc-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-teal-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.min((bar.current / bar.max) * 100, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
