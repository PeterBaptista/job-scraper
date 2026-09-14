"""Placeholder resume — copy to resumes/clean/content.py and fill in with real data.

resumes/clean/ and every other stack folder are git-ignored: resume content is personal.
"""

_EN = {
    "title": "Full Stack Developer",
    "location": "City, Country (Remote)",
    "h_summary": "SUMMARY",
    "h_experience": "EXPERIENCE",
    "h_skills": "SKILLS",
    "h_projects": "PROJECTS",
    "h_education": "EDUCATION",
    "summary": "Two or three sentences with the keywords of the roles you target.",
    "skills": [
        ("Languages", "TypeScript, Python"),
        ("Frontend", "React, Next.js"),
        ("Backend", "Node.js, FastAPI"),
        ("Databases", "PostgreSQL"),
    ],
    "experience": [
        {
            "title": "Software Developer",
            "company": "Company Name",
            "period": "2023 – Present",
            "bullets": [
                "What you built, how it was measured, and how you did it.",
            ],
        },
    ],
    "projects": [],
    "education": [
        {
            "degree": "Bachelor of Computer Science",
            "institution": "University Name",
            "period": "2020 – 2024",
        },
    ],
}

CONTENT = {
    "en": _EN,
    "pt": {
        **_EN,
        "title": "Desenvolvedor Full Stack",
        "location": "Cidade, País (Remoto)",
        "h_summary": "RESUMO",
        "h_experience": "EXPERIÊNCIA",
        "h_skills": "HABILIDADES",
        "h_projects": "PROJETOS",
        "h_education": "FORMAÇÃO",
    },
}
