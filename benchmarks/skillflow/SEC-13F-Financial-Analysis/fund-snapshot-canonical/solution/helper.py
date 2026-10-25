"""Canonical SEC reference, derived from the task's stated rules and input TSVs."""
from __future__ import annotations

import collections
import csv
import math
from pathlib import Path

SUFFIXES = set("llc lp ltd inc corp corporation company co partners management advisors capital group holdings".split())
INCLUDE = ("stock", "share", "ordinary", "common")
EXCLUDE = ("preferred", "option", "warrant", "right", "debt", "note", "bond", "put", "call")


def normalize(text):
    words = "".join(c for c in str(text).lower() if c.isalnum() or c.isspace()).split()
    while words and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)


def distance(left, right):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def stock_like(label):
    label = str(label).lower()
    return any(word in label for word in INCLUDE) and not any(word in label for word in EXCLUDE)


def compute(root):
    root = Path(root) / "2025-q3"
    with (root / "COVERPAGE.tsv").open(encoding="utf-8-sig", newline="") as handle:
        cover = list(csv.DictReader(handle, delimiter="\t"))
    query = "renaissance technologies"
    fund = min(cover, key=lambda row: (distance(normalize(query), normalize(row["FILINGMANAGER_NAME"])),
                                       row["FILINGMANAGER_NAME"].casefold(), row["FILINGMANAGER_NAME"]))
    with (root / "INFOTABLE.tsv").open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle, delimiter="\t")
                if row["ACCESSION_NUMBER"] == fund["ACCESSION_NUMBER"]]
    stocks = [row for row in rows if stock_like(row["TITLEOFCLASS"])]
    grouped = collections.defaultdict(list)
    for row in stocks:
        grouped[row["CUSIP"]].append(float(row["VALUE"]))
    ranked = sorted(grouped, key=lambda cusip: (-math.fsum(grouped[cusip]), cusip))
    return {"fund_query": query, "quarter": "2025-q3", "matched_manager": fund["FILINGMANAGER_NAME"],
            "accession_number": fund["ACCESSION_NUMBER"], "aum": math.fsum(float(row["VALUE"]) for row in rows),
            "stock_holdings": len(stocks), "stock_aum": math.fsum(float(row["VALUE"]) for row in stocks),
            "top3_cusips_by_value": ranked[:3]}
