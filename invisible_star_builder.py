#!/usr/bin/env python3
"""Invisible STAR Interview Builder (Government Jobs).

A lightweight CLI tool that:
1) Parses a job posting.
2) Extracts duty statement percentages.
3) Maps experience bullets to duty areas.
4) Produces interview-ready STAR answers in a natural voice.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DUTY_HEADER_RE = re.compile(
    r"^(?:duty\s*statement|essential\s*functions?|responsibilit(?:y|ies)|tasks?)",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"(?P<pct>\d{1,3})\s*%")


@dataclass
class DutyItem:
    title: str
    percent: int
    context: str


@dataclass
class ExperienceItem:
    raw: str
    keywords: set[str]


def normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9\-]+", text.lower())


def build_keywords(text: str) -> set[str]:
    words = normalize_words(text)
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "from",
        "this",
        "into",
        "your",
        "our",
        "you",
        "were",
        "when",
        "while",
        "have",
        "has",
        "had",
        "not",
        "are",
        "was",
        "but",
        "job",
        "duty",
        "statement",
        "percent",
    }
    return {w for w in words if len(w) > 2 and w not in stopwords}


def split_blocks(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]


def extract_duties(job_posting: str) -> list[DutyItem]:
    duties: list[DutyItem] = []
    lines = [line.strip(" -•\t") for line in job_posting.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        pct_match = PERCENT_RE.search(line)
        if not pct_match:
            continue

        pct = int(pct_match.group("pct"))
        if pct > 100:
            continue

        # Prefer the current line as title, fallback to previous line if this looks like pure percentage.
        title = re.sub(r"^\s*\d{1,3}\s*%\s*", "", line).strip() or line
        if line.strip().replace("%", "").isdigit() and i > 0:
            title = lines[i - 1]

        context_window = " ".join(lines[max(0, i - 1) : min(len(lines), i + 2)])
        duties.append(DutyItem(title=title, percent=pct, context=context_window))

    # If no explicit percentages were detected, create fallback duties from likely responsibility blocks.
    if not duties:
        blocks = split_blocks(job_posting)
        inferred = []
        for block in blocks:
            first = block.splitlines()[0].strip()
            if DUTY_HEADER_RE.search(first) or len(block.split()) > 25:
                inferred.append(first)
        if not inferred:
            inferred = [b.splitlines()[0] for b in blocks[:3]]

        default_pct = max(1, 100 // max(1, len(inferred)))
        duties = [DutyItem(title=x, percent=default_pct, context=x) for x in inferred[:6]]

    duties.sort(key=lambda d: d.percent, reverse=True)
    return duties


def parse_experience(experience_text: str) -> list[ExperienceItem]:
    entries: list[ExperienceItem] = []
    for raw in re.split(r"\n[-•]|\n\d+\.", experience_text.strip()):
        cleaned = raw.strip(" -•\n\t")
        if not cleaned:
            continue
        entries.append(ExperienceItem(raw=cleaned, keywords=build_keywords(cleaned)))
    return entries


def score_match(duty: DutyItem, exp: ExperienceItem) -> int:
    duty_keywords = build_keywords(duty.context)
    overlap = duty_keywords.intersection(exp.keywords)
    return len(overlap)


def select_best_experience(duty: DutyItem, experience: Iterable[ExperienceItem]) -> ExperienceItem | None:
    ranked = sorted(experience, key=lambda x: score_match(duty, x), reverse=True)
    return ranked[0] if ranked else None


def naturalize_sentence(text: str) -> str:
    replacements = {
        "leveraged": "used",
        "utilized": "used",
        "facilitated": "helped",
        "implemented": "put in place",
        "optimized": "improved",
        "stakeholders": "partners",
        "cross-functional": "across teams",
        "synergy": "coordination",
        "robust": "solid",
    }
    out = text
    for src, dest in replacements.items():
        out = re.sub(rf"\b{re.escape(src)}\b", dest, out, flags=re.IGNORECASE)
    return out


def build_star_answer(duty: DutyItem, exp: ExperienceItem | None) -> str:
    if exp is None:
        return (
            f"**Duty focus ({duty.percent}%):** {duty.title}\n"
            "- **Situation:** In prior roles, I handled similar responsibility areas.\n"
            "- **Task:** Deliver results aligned with policy, timelines, and service standards.\n"
            "- **Action:** I built a work plan, coordinated with teammates, and tracked deliverables.\n"
            "- **Result:** Work was completed on time with fewer handoff issues and clearer accountability."
        )

    source = naturalize_sentence(exp.raw).rstrip(". ")
    return (
        f"**Duty focus ({duty.percent}%):** {duty.title}\n"
        f"- **Situation:** A key assignment came up related to {duty.title.lower().rstrip('.')}.\n"
        "- **Task:** I needed to deliver a reliable outcome while keeping communication clear and timelines realistic.\n"
        f"- **Action:** I {source[0].lower() + source[1:] if len(source) > 1 else source}. I documented progress, addressed risks early, and adjusted the plan when priorities shifted.\n"
        "- **Result:** The final outcome met requirements, improved turnaround for the team, and gave leaders confidence in execution."
    )


def render_output(duties: list[DutyItem], experiences: list[ExperienceItem], top_n: int) -> str:
    lines = ["# Invisible STAR Interview Builder", ""]
    lines.append("## Duty Statement Breakdown")
    for i, duty in enumerate(duties[:top_n], start=1):
        lines.append(f"{i}. {duty.percent}% — {duty.title}")

    lines.append("")
    lines.append("## STAR Interview Answers")
    for duty in duties[:top_n]:
        best = select_best_experience(duty, experiences)
        lines.append(build_star_answer(duty, best))
        lines.append("")

    lines.append("## Tone Notes (Anti-Robotic)")
    lines.append("- Use real details: numbers, systems, deadlines, and who benefited.")
    lines.append("- Keep sentences short and direct.")
    lines.append("- Replace buzzwords with plain language and concrete actions.")
    return "\n".join(lines).strip() + "\n"


def read_text(path_or_text: str) -> str:
    path = Path(path_or_text)
    return path.read_text(encoding="utf-8") if path.exists() else path_or_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Build duty-aligned STAR answers for government job interviews.")
    parser.add_argument("--job", required=True, help="Path to job posting text file or raw text.")
    parser.add_argument("--experience", required=True, help="Path to your experience bullet points file or raw text.")
    parser.add_argument("--top", type=int, default=5, help="Number of top duty items to generate (default: 5).")
    parser.add_argument("--out", help="Optional output markdown file path.")
    args = parser.parse_args()

    job_text = read_text(args.job)
    exp_text = read_text(args.experience)

    duties = extract_duties(job_text)
    experiences = parse_experience(exp_text)
    output = render_output(duties=duties, experiences=experiences, top_n=max(1, args.top))

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Saved output to {args.out}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
