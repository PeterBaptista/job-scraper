'use client';

import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Spinner } from '@/components/ui/spinner';
import { JobRow } from './job-row';
import { Empty, EmptyMedia, EmptyHeader, EmptyTitle, EmptyDescription } from '@/components/ui/empty';
import { Briefcase } from 'lucide-react';
import type { Job } from '@/lib/types/job.types';

interface JobsTableProps {
  jobs: Job[];
  isLoading?: boolean;
}

export function JobsTable({ jobs, isLoading }: JobsTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }
  
  if (jobs.length === 0) {
    return (
      <Empty>
        <EmptyMedia variant="icon">
          <Briefcase />
        </EmptyMedia>
        <EmptyHeader>
          <EmptyTitle>No jobs found</EmptyTitle>
          <EmptyDescription>Try adjusting your filters or start a new scraping session.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50 hover:bg-muted/50">
            <TableHead className="w-[280px]">Job</TableHead>
            <TableHead className="w-[180px]">Location</TableHead>
            <TableHead className="w-[100px]">Source</TableHead>
            <TableHead className="w-[120px]">Status</TableHead>
            <TableHead className="w-[150px]">Salary</TableHead>
            <TableHead className="w-[100px]">Scraped</TableHead>
            <TableHead className="w-[100px] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job) => (
            <JobRow key={job.id} job={job} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
