# Scraper service — FastAPI consumer + scheduler, driving real Chrome under Xvfb.
#
# Headed Chrome (not headless) is deliberate: SeleniumBase UC mode's anti-detection
# relies on a real browser, and headless Chrome is trivially fingerprinted. Xvfb gives
# it a virtual display so it runs in a container with no monitor attached.
# Not -slim: SeleniumBase's Xvfb path imports pyautogui -> MouseInfo, which calls
# sys.exit() when tkinter is missing. The full image ships tkinter; the slim one
# doesn't, and apt's python3-tk targets a different interpreter than this one.
FROM python:3.12

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# xvfb + the shared libraries Chrome needs. wget/gnupg are only for fetching Chrome.
# xauth is required alongside xvfb — without it SeleniumBase logs
# "X11 display failed!" and silently falls back to a non-Xvfb browser.
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates gnupg xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

# Installing the .deb via apt pulls in Chrome's remaining runtime deps automatically.
RUN wget -q -O /tmp/chrome.deb \
        https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so code edits don't bust the layer cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Chrome's sandbox refuses to run as root. Using an unprivileged user keeps the
# sandbox enabled, which is both safer and less detectable than --no-sandbox.
RUN useradd --create-home --uid 1000 scraper \
    && mkdir -p /app/cookies /app/downloaded_files \
    && chown -R scraper:scraper /app
USER scraper

ENV PATH="/app/.venv/bin:$PATH" \
    HOME=/home/scraper

# Fetch the UC-mode driver at build time. Otherwise every container recreate
# re-downloads it on the first scrape, and a hiccup at the registry becomes a
# failed run rather than a failed build.
RUN sbase get uc_driver && sbase get chromedriver

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
