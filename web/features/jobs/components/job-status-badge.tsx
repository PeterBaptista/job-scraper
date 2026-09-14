'use client';

import { Badge } from '@/components/ui/badge';
import type { JobStatus } from '@/lib/types/job.types';

interface JobStatusBadgeProps {
  status: JobStatus;
}

const statusConfig: Record<JobStatus, { label: string; className: string }> = {
  new: {
    label: 'New',
    className: 'bg-chart-1/20 text-chart-1 border-chart-1/30',
  },
  viewed: {
    label: 'Viewed',
    className: 'bg-muted text-muted-foreground border-border',
  },
  applied: {
    label: 'Applied',
    className: 'bg-chart-2/20 text-chart-2 border-chart-2/30',
  },
  interviewing: {
    label: 'Interviewing',
    className: 'bg-chart-3/20 text-chart-3 border-chart-3/30',
  },
  rejected: {
    label: 'Rejected',
    className: 'bg-destructive/20 text-destructive border-destructive/30',
  },
  offer: {
    label: 'Offer',
    className: 'bg-success/20 text-success border-success/30',
  },
};

export function JobStatusBadge({ status }: JobStatusBadgeProps) {
  const config = statusConfig[status];
  
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  );
}
