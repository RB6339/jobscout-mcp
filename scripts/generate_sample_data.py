"""Generate a reproducible, fully synthetic job dataset for demos and tests.

All companies and postings are fictional. Replace with your own data via
scripts/import_csv.py if you want to analyse real postings you have exported.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

COMPANIES = [
    "Nimbus Analytics", "Quanta Labs", "Bluefin AI", "Orbit Fintech", "Lattice Health",
    "Vertex Retail Tech", "Kestrel Robotics", "Saffron Data", "Monsoon Systems", "Indigo Cloud",
    "Pinecrest Insurance", "Tidal Media", "Cobalt Logistics", "Helix Bio AI", "Aurora EdTech",
]
LOCATIONS = ["Pune", "Bengaluru", "Hyderabad", "Mumbai", "Chennai", "Gurugram", "Noida", "Remote"]

ROLES = {
    "Data Scientist": ["python", "sql", "machine learning", "statistics", "pandas", "scikit-learn", "nlp"],
    "Machine Learning Engineer": ["python", "pytorch", "docker", "kubernetes", "mlflow", "aws", "fastapi"],
    "Generative AI Engineer": ["python", "llm", "rag", "langchain", "vector database", "openai api", "prompt engineering"],
    "Agentic AI Engineer": ["python", "langgraph", "mcp", "tool calling", "llm", "fastapi", "aws"],
    "NLP Engineer": ["python", "nlp", "transformers", "hugging face", "pytorch", "text classification"],
    "MLOps Engineer": ["python", "docker", "kubernetes", "mlflow", "ci/cd", "aws", "terraform"],
    "AI Engineer": ["python", "llm", "rag", "fastapi", "docker", "azure", "langchain"],
}
EXTRA_SKILLS = ["gcp", "azure", "aws", "spark", "airflow", "redis", "mongodb", "pgvector", "evaluation", "git"]
EXP_BANDS = [(0, 2), (1, 3), (2, 4), (2, 5), (3, 5), (3, 6), (4, 8), (5, 10)]


def make_job(i: int, today: date) -> dict:
    title = random.choice(list(ROLES))
    skills = random.sample(ROLES[title], k=min(5, len(ROLES[title])))
    skills += random.sample(EXTRA_SKILLS, k=2)
    lo, hi = random.choice(EXP_BANDS)
    sal_lo = round(4 + lo * 2.5 + random.uniform(0, 2), 1)
    sal_hi = round(sal_lo + random.uniform(3, 8), 1)
    location = random.choice(LOCATIONS)
    company = random.choice(COMPANIES)
    return {
        "id": f"JS-{1000 + i}",
        "title": title,
        "company": company,
        "location": location,
        "remote": location == "Remote" or random.random() < 0.15,
        "min_exp": lo,
        "max_exp": hi,
        "salary_min_lpa": sal_lo,
        "salary_max_lpa": sal_hi,
        "skills": sorted(set(skills)),
        "description": (
            f"{company} is hiring a {title} ({lo}-{hi} yrs) in {location}. "
            f"You will work with {', '.join(skills[:4])} to ship production AI systems."
        ),
        "posted_date": (today - timedelta(days=random.randint(0, 20))).isoformat(),
    }


def main() -> None:
    today = date(2026, 11, 1)
    jobs = [make_job(i, today) for i in range(60)]
    out = Path(__file__).resolve().parents[1] / "data" / "jobs_sample.json"
    out.write_text(json.dumps(jobs, indent=2))
    print(f"wrote {len(jobs)} synthetic jobs to {out}")


if __name__ == "__main__":
    main()
