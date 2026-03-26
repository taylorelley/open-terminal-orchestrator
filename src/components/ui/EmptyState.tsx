import { type ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="p-4 bg-zinc-100 rounded-2xl text-zinc-400 mb-4">{icon}</div>
      <h3 className="text-lg font-semibold text-zinc-900 mb-1">{title}</h3>
      <p className="text-sm text-zinc-500 text-center max-w-sm mb-4">{description}</p>
      {action}
    </div>
  );
}

export function LoadingState({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="animate-pulse flex gap-4 items-center">
          <div className="h-4 bg-zinc-200 rounded w-24" />
          <div className="h-4 bg-zinc-100 rounded flex-1" />
          <div className="h-4 bg-zinc-100 rounded w-20" />
          <div className="h-4 bg-zinc-100 rounded w-16" />
        </div>
      ))}
    </div>
  );
}
