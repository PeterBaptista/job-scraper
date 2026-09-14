'use client';

import { TableCell, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ExternalLink, FileText, MoreHorizontal, Check, Eye, X, MessageSquare, Trophy } from 'lucide-react';
import Link from 'next/link';
import { JobStatusBadge } from './job-status-badge';
import { JobSourceBadge } from './job-source-badge';
import { useApplyToJob, useUpdateJobStatus } from '../hooks/use-job-mutations';
import type { Job, JobStatus } from '@/lib/types/job.types';
import { formatDistanceToNow } from '@/lib/utils/date';

interface JobRowProps {
  job: Job;
}

export function JobRow({ job }: JobRowProps) {
  const applyMutation = useApplyToJob();
  const updateStatusMutation = useUpdateJobStatus();
  
  const handleApply = () => {
    applyMutation.mutate(job.id);
  };
  
  const handleStatusChange = (status: JobStatus) => {
    updateStatusMutation.mutate({ id: job.id, status });
  };
  
  return (
    <TableRow className="hover:bg-accent/50 transition-colors">
      <TableCell className="py-4">
        <div className="flex flex-col gap-1">
          <span className="font-medium text-foreground">{job.title}</span>
          <span className="text-sm text-muted-foreground">{job.company}</span>
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground">{job.location}</TableCell>
      <TableCell>
        <JobSourceBadge source={job.source} />
      </TableCell>
      <TableCell>
        <JobStatusBadge status={job.status} />
      </TableCell>
      <TableCell className="text-muted-foreground text-sm">
        {job.salary || '-'}
      </TableCell>
      <TableCell className="text-muted-foreground text-sm">
        {formatDistanceToNow(job.scrapedAt)}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            asChild
            className="h-8 px-2"
            title="Editar o CV desta vaga"
          >
            <Link href={`/jobs/${job.id}/resume`}>
              <FileText className="h-4 w-4" />
            </Link>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            asChild
            className="h-8 px-2"
          >
            <a href={job.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 px-2">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {job.status !== 'applied' && (
                <DropdownMenuItem onClick={handleApply}>
                  <Check className="mr-2 h-4 w-4" />
                  Mark as Applied
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={() => handleStatusChange('viewed')}>
                <Eye className="mr-2 h-4 w-4" />
                Mark as Viewed
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleStatusChange('interviewing')}>
                <MessageSquare className="mr-2 h-4 w-4" />
                Mark as Interviewing
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => handleStatusChange('offer')}>
                <Trophy className="mr-2 h-4 w-4" />
                Mark as Offer
              </DropdownMenuItem>
              <DropdownMenuItem 
                onClick={() => handleStatusChange('rejected')}
                className="text-destructive focus:text-destructive"
              >
                <X className="mr-2 h-4 w-4" />
                Mark as Rejected
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </TableCell>
    </TableRow>
  );
}
