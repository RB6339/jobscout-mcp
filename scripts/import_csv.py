"""Import your own job postings from a CSV into the JobScout database.

Expected columns: id,title,company,location,remote,min_exp,max_exp,
salary_min_lpa,salary_max_lpa,skills,description,posted_date
`skills` is a semicolon-separated list, e.g. "python;rag;langchain".

    python scripts/import_csv.py my_jobs.csv
"""

import csv
import sys

from jobscout import db


def main(path: str) -> None:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    jobs = [{**r, "remote": r.get("remote", "").strip().lower() in {"1", "true", "yes"},
             "skills": [s for s in r.get("skills", "").split(";") if s.strip()],
             "salary_min_lpa": float(r["salary_min_lpa"]) if r.get("salary_min_lpa") else None,
             "salary_max_lpa": float(r["salary_max_lpa"]) if r.get("salary_max_lpa") else None}
            for r in rows]
    n = db.load_jobs(db.connect(), jobs)
    print(f"imported {n} jobs")


if __name__ == "__main__":
    main(sys.argv[1])
