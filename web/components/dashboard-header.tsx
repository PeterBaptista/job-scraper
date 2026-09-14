import { Briefcase } from 'lucide-react';

export function DashboardHeader() {
  return (
    <header className="border-b border-border bg-card">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary p-2">
            <Briefcase className="h-5 w-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Job Scraper</h1>
            <p className="text-xs text-muted-foreground">
              Track and manage scraped job opportunities
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
