from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": the .env file is shared with other tooling, and pydantic-settings
    # raises extra_forbidden on any key it does not declare (OPENAI_API_KEY did exactly
    # that and broke every host script while the container kept running).
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    rabbitmq_url: str = "amqp://jobscraper:jobscraper@localhost:5672/"
    database_url: str = "postgresql://jobscraper:jobscraper@localhost:5432/jobscraper"
    scrape_queue: str = "scrape_jobs"
    cookies_dir: str = "cookies"

    # Run headed Chrome inside a virtual framebuffer (containers have no display).
    # Real headed Chrome under Xvfb keeps UC mode's anti-detection; headless does not.
    browser_xvfb: bool = False

    # Telegram notifications
    telegram_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = True

    # Hourly scrape scheduler
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 60
    scheduler_jitter_minutes: int = 12          # actual interval: 48-72 min
    scheduler_source: str = "linkedin"
    scheduler_time_posted_seconds: int = 7200   # LinkedIn f_TPR=r7200 (last 2h)
    scheduler_user_email: str = ""              # blank -> resolve the sole user in the DB

    # OpenAI — resume tailoring and external-form field mapping
    openai_api_key: str = ""
    openai_model: str = "gpt-5.1"
    # Form field mapping is mechanical label->value matching, not prose that lands
    # on an employer's desk — a smaller model is enough and much cheaper per call.
    openai_form_model: str = "gpt-5-mini"

    # Auto-apply
    apply_enabled: bool = True
    apply_dry_run: bool = True          # fill everything, stop before final submit
    apply_queue: str = "apply_jobs"
    # 40, not 60: a real fullstack role the candidate actually applied to scores 44 —
    # it asks for a lot he lacks, which is real signal, but he still wanted it.
    # 40 keeps stretch roles while filtering the 0-score iOS/Golang/data noise.
    ats_min_score: int = 40
    # The score labels the card ("low match") instead of blocking it: a tailored CV
    # is produced for every job, because a low score is information for the reader,
    # not a reason to withhold the document. Set true to restore hard gating.
    ats_gate_enabled: bool = False
    # Optimisation passes per job: tailor -> score -> feed the still-missing terms
    # back -> keep the best truthful version. Each pass is another OpenAI call, so
    # this multiplies cost; it stops early when nothing left is coverable.
    ats_max_passes: int = 3
    # Companies never surfaced in Telegram (comma-separated, substring match).
    # They stay in the database; they just don't reach the phone or cost a
    # tailoring call. High-volume outsourcers can otherwise dominate the feed.
    blocked_companies: str = ""
    resume_out_dir: str = "generated_resumes"
    answers_file: str = "answers.yml"
    # Where the web dashboard lives. Telegram cards deep-link into it instead of
    # attaching a PDF, so a CV can be corrected rather than arriving final.
    dashboard_url: str = "http://localhost:3000"
    # Shared secret for the resume API. The web app proxies every call and adds
    # this header; port 8000 is published to the host, so without a token the
    # render endpoints would be open to anything that can reach the port. Blank
    # means the router refuses to mount — fail closed, never silently open.
    internal_api_token: str = ""


settings = Settings()
