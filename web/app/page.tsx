import { DashboardHeader } from '@/components/dashboard-header';
import { DashboardContent } from '@/components/dashboard-content';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader />
      <DashboardContent />
    </div>
  );
}
