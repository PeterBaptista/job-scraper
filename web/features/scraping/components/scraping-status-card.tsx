'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { RefreshCw, ChevronDown, Loader2 } from 'lucide-react';
import { useStartScraping } from '../hooks/use-start-scraping';
import { useScrapingStatus } from '../hooks/use-scraping-status';
import { ScrapingProgress } from './scraping-progress';
import type { JobSource } from '@/lib/types/job.types';

const sources: { value: JobSource; label: string }[] = [
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'glassdoor', label: 'Glassdoor' },
  { value: 'indeed', label: 'Indeed' },
];

export function ScrapingStatusCard() {
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const startScrapingMutation = useStartScraping();
  const { data: scrapingJob } = useScrapingStatus(activeJobId);
  
  const handleStartScraping = async (source: JobSource) => {
    try {
      const result = await startScrapingMutation.mutateAsync(source);
      setActiveJobId(result.id);
    } catch (error) {
      console.error('Failed to start scraping:', error);
    }
  };
  
  const isScrapingInProgress = scrapingJob && 
    (scrapingJob.status === 'queued' || scrapingJob.status === 'processing');
  
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">Scraping</CardTitle>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                size="sm" 
                disabled={isScrapingInProgress || startScrapingMutation.isPending}
              >
                {isScrapingInProgress || startScrapingMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Start Scraping
                <ChevronDown className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {sources.map((source) => (
                <DropdownMenuItem
                  key={source.value}
                  onClick={() => handleStartScraping(source.value)}
                >
                  Scrape {source.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent>
        {scrapingJob ? (
          <ScrapingProgress job={scrapingJob} />
        ) : (
          <p className="text-sm text-muted-foreground">
            No active scraping job. Start one to find new opportunities.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
