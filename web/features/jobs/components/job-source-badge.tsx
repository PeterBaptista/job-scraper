'use client';

import { Badge } from '@/components/ui/badge';
import type { JobSource } from '@/lib/types/job.types';

interface JobSourceBadgeProps {
  source: JobSource;
}

const sourceConfig: Record<JobSource, { label: string; className: string }> = {
  linkedin: {
    label: 'LinkedIn',
    className: 'bg-[#0A66C2]/20 text-[#0A66C2] border-[#0A66C2]/30',
  },
  glassdoor: {
    label: 'Glassdoor',
    className: 'bg-[#0CAA41]/20 text-[#0CAA41] border-[#0CAA41]/30',
  },
  indeed: {
    label: 'Indeed',
    className: 'bg-[#2164F3]/20 text-[#2164F3] border-[#2164F3]/30',
  },
  other: {
    label: 'Other',
    className: 'bg-muted text-muted-foreground border-border',
  },
};

export function JobSourceBadge({ source }: JobSourceBadgeProps) {
  const config = sourceConfig[source];
  
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  );
}
