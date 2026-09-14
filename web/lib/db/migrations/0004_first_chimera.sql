CREATE TABLE "resume_draft" (
	"id" text PRIMARY KEY NOT NULL,
	"job_id" text NOT NULL,
	"user_id" text NOT NULL,
	"status" text DEFAULT 'tailoring' NOT NULL,
	"language" text DEFAULT 'pt' NOT NULL,
	"content" jsonb,
	"generated_content" jsonb,
	"meta" jsonb,
	"ats_score" integer,
	"ats_detail" jsonb,
	"extra_prompt" text,
	"error" text,
	"pdf_path" text,
	"pdf_committed_at" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "resume_draft" ADD CONSTRAINT "resume_draft_job_id_job_id_fk" FOREIGN KEY ("job_id") REFERENCES "public"."job"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "resume_draft" ADD CONSTRAINT "resume_draft_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE UNIQUE INDEX "resume_draft_job_idx" ON "resume_draft" USING btree ("job_id");