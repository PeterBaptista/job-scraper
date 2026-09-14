'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Briefcase, Sparkles, Send, MessageSquare, XCircle, Trophy } from 'lucide-react';
import type { JobStats } from '@/lib/types/job.types';

interface JobStatsCardsProps {
  stats: JobStats;
}

const statsConfig = [
  {
    key: 'total' as const,
    label: 'Total Jobs',
    icon: Briefcase,
    className: 'text-foreground',
  },
  {
    key: 'new' as const,
    label: 'New',
    icon: Sparkles,
    className: 'text-chart-1',
  },
  {
    key: 'applied' as const,
    label: 'Applied',
    icon: Send,
    className: 'text-chart-2',
  },
  {
    key: 'interviewing' as const,
    label: 'Interviewing',
    icon: MessageSquare,
    className: 'text-chart-3',
  },
  {
    key: 'rejected' as const,
    label: 'Rejected',
    icon: XCircle,
    className: 'text-destructive',
  },
  {
    key: 'offer' as const,
    label: 'Offers',
    icon: Trophy,
    className: 'text-success',
  },
];

export function JobStatsCards({ stats }: JobStatsCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
      {statsConfig.map((config) => {
        const Icon = config.icon;
        return (
          <Card key={config.key} className="bg-card border-border">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className={`rounded-lg bg-muted p-2 ${config.className}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{stats[config.key]}</p>
                  <p className="text-xs text-muted-foreground">{config.label}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
