"""
score_jobs.py — LLM-based job fit scoring via Anthropic Claude.

Sends each job posting + private candidate profile to the model and
returns a structured JSON score: fit_score, verdict, reasons, concerns.
"""
import json
import time
import logging
from typing import Dict, Optional

import anthropic

logger = logging.getLogger(__name__)

_PROMPT = """\
You are evaluating job fit for a candidate. Be concise and honest.

=== CANDIDATE PROFILE ===
{profile_summary}

=== JOB POSTING ===
Title:    {title}
Company:  {company}
Location: {location}

Description:
{description}

=== TASK ===
Score how well this job matches the candidate. Consider:
- Direct relevance of the role to the candidate's core expertise
- Technology / tool overlap
- Industry and domain alignment
- Seniority level match
- Any explicit preferences or deal-breakers stated in the profile

Return ONLY a valid JSON object — no markdown fences, no explanation text:
{{
  "fit_score": <integer 0-100>,
  "verdict": "<strong | maybe | weak>",
  "reasons":  ["<up to 3 key fit points>"],
  "concerns": ["<up to 3 key concerns or gaps>"]
}}

Scoring guide:
  80-100 → strong:  excellent match, clearly relevant
  60-79  → maybe:   good match, worth applying
  40-59  → partial: some relevant aspects but notable gaps
  0-39   → weak:    not a good match
"""


def score_job(
    job: Dict,
    profile_summary: str,
    model: str = "claude-sonnet-4-5",
    retries: int = 2,
) -> Optional[Dict]:
    """
    Score a single job against the candidate profile.

    Returns a dict with keys: fit_score, verdict, reasons, concerns.
    Returns None if all attempts fail.
    """
    client = anthropic.Anthropic()

    prompt = _PROMPT.format(
        profile_summary=profile_summary.strip(),
        title=job.get("title")       or "(not provided)",
        company=job.get("company")   or "(not provided)",
        location=job.get("location") or "(not provided)",
        description=(job.get("description") or "(not provided)")[:3500],
    )

    for attempt in range(retries + 1):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=600,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()

            # Robustly extract the JSON block even if model adds surrounding text
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start < 0 or end <= start:
                raise ValueError(f"No JSON object found in response: {raw[:300]}")

            result = json.loads(raw[start:end])

            # Normalise / validate
            result["fit_score"] = max(0, min(100, int(result.get("fit_score", 0))))
            result["verdict"]   = str(result.get("verdict", "weak")).lower()
            result.setdefault("reasons",  [])
            result.setdefault("concerns", [])
            return result

        except json.JSONDecodeError as e:
            logger.warning("JSON decode error (attempt %d/%d): %s", attempt + 1, retries + 1, e)
        except Exception as e:
            logger.warning("Scoring error (attempt %d/%d): %s", attempt + 1, retries + 1, e)

        if attempt < retries:
            time.sleep(2 ** attempt)   # exponential back-off

    logger.error("All scoring attempts failed for: %s", job.get("title"))
    return None
