import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { DashboardHeader } from '@/components/dashboard-header';
import { Button } from '@/components/ui/button';
import { requireSession } from '@/lib/auth/get-session';
import { jobService } from '@/lib/services/job.service';
import { ResumeEditor } from '@/features/resume/components/resume-editor';

export default async function ResumePage({ params }: { params: Promise<{ id: string }> }) {
  const [{ user }, { id }] = await Promise.all([requireSession(), params]);
  const job = await jobService.getJobById(user.id, id);

  if (!job) notFound();

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader />
      <div className="border-b px-4 py-2">
        <Button asChild variant="ghost" size="sm">
          <Link href="/">
            <ArrowLeft className="mr-1 h-4 w-4" />
            Voltar para as vagas
          </Link>
        </Button>
      </div>
      <ResumeEditor job={job} />
    </div>
  );
}
