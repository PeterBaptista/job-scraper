'use client';

import { Progress } from '@/components/ui/progress';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import type { ScrapingJob } from '@/lib/types/job.types';

interface ScrapingProgressProps {
  job: ScrapingJob;
}

export function ScrapingProgress({ job }: ScrapingProgressProps) {
  const getStatusIcon = () => {
    switch (job.status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-success" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-destructive" />;
      default:
        return <Loader2 className="h-4 w-4 animate-spin text-chart-1" />;
    }
  };
  
  const getSourceLabel = () => {
    const labels: Record<string, string> = {
      linkedin: 'LinkedIn',
      glassdoor: 'Glassdoor',
      indeed: 'Indeed',
      other: 'Other',
    };
    return labels[job.source] || job.source;
  };
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className="text-sm font-medium">{getSourceLabel()}</span>
        </div>
        <span className="text-sm text-muted-foreground">{job.progress}%</span>
      </div>
      <Progress value={job.progress} className="h-2" />
      {job.message && (
        <p className="text-xs text-muted-foreground">{job.message}</p>
      )}
      {job.status === 'completed' && job.jobsFound !== undefined && (
        <p className="text-xs text-success">
          Found {job.jobsFound} new jobs
        </p>
      )}
    </div>
  );
}
