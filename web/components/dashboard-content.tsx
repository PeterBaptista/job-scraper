'use client';

import { useState } from 'react';
import { JobsTable } from '@/features/jobs/components/jobs-table';
import { JobFilters } from '@/features/jobs/components/job-filters';
import { JobStatsCards } from '@/features/jobs/components/job-stats-cards';
import { ScrapingStatusCard } from '@/features/scraping/components/scraping-status-card';
import { useJobs } from '@/features/jobs/hooks/use-jobs';
import type { JobFilters as JobFiltersType } from '@/lib/types/job.types';

export function DashboardContent() {
  const [filters, setFilters] = useState<JobFiltersType>({});
  const { data, isLoading } = useJobs(filters);
  
  const jobs = data?.jobs || [];
  const stats = data?.stats || {
    total: 0,
    new: 0,
    applied: 0,
    interviewing: 0,
    rejected: 0,
    offer: 0,
  };
  
  return (
    <main className="container mx-auto px-4 py-6 space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <JobStatsCards stats={stats} />
        <ScrapingStatusCard />
      </div>
      
      <section className="space-y-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Job Listings</h2>
            <p className="text-sm text-muted-foreground">
              {jobs.length} jobs found
            </p>
          </div>
          <JobFilters filters={filters} onFiltersChange={setFilters} />
        </div>
        
        <JobsTable jobs={jobs} isLoading={isLoading} />
      </section>
    </main>
  );
}
