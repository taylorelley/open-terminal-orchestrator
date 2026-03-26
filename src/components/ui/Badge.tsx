import type { SandboxState, PolicyTier, OwuiRole } from '../../types';

const stateColors: Record<SandboxState, string> = {
  POOL: 'bg-zinc-100 text-zinc-700',
  WARMING: 'bg-amber-100 text-amber-800',
  READY: 'bg-teal-100 text-teal-800',
  ACTIVE: 'bg-emerald-100 text-emerald-800',
  SUSPENDED: 'bg-orange-100 text-orange-800',
  DESTROYED: 'bg-red-100 text-red-800',
};

const tierColors: Record<PolicyTier, string> = {
  restricted: 'bg-amber-100 text-amber-800',
  standard: 'bg-teal-100 text-teal-800',
  elevated: 'bg-sky-100 text-sky-800',
};

const roleColors: Record<OwuiRole, string> = {
  admin: 'bg-sky-100 text-sky-800',
  user: 'bg-zinc-100 text-zinc-700',
  pending: 'bg-amber-100 text-amber-800',
};

const eventColors: Record<string, string> = {
  allow: 'bg-teal-100 text-teal-800',
  deny: 'bg-red-100 text-red-800',
  route: 'bg-sky-100 text-sky-800',
  created: 'bg-emerald-100 text-emerald-800',
  assigned: 'bg-teal-100 text-teal-800',
  suspended: 'bg-orange-100 text-orange-800',
  resumed: 'bg-teal-100 text-teal-800',
  destroyed: 'bg-red-100 text-red-800',
  policy_change: 'bg-sky-100 text-sky-800',
  config_change: 'bg-zinc-100 text-zinc-700',
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'state' | 'tier' | 'role' | 'event';
  value?: string;
  className?: string;
}

export function Badge({ children, variant = 'default', value, className = '' }: BadgeProps) {
  let colorClass = 'bg-zinc-100 text-zinc-700';

  if (variant === 'state' && value) colorClass = stateColors[value as SandboxState] || colorClass;
  else if (variant === 'tier' && value) colorClass = tierColors[value as PolicyTier] || colorClass;
  else if (variant === 'role' && value) colorClass = roleColors[value as OwuiRole] || colorClass;
  else if (variant === 'event' && value) colorClass = eventColors[value] || colorClass;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${colorClass} ${className}`}
    >
      {children}
    </span>
  );
}
