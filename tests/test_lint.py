import pytest
from core.lint import lint_prompt, lint_skill


def test_lint_prompt_clean():
    clean_prompt = """
You are an invoice parser.
Extract the vendor, date, and total amount into valid JSON format.

Rules:
1. Return ONLY valid JSON schema {"vendor": string, "date": string, "amount": float}.
2. If the document is unreadable or not an invoice, refuse to process and return {"error": "out of scope"}.

Input:
\"\"\"{input}\"\"\"
"""
    findings = lint_prompt(clean_prompt)
    errors = [f for f in findings if f["severity"] == "error"]
    assert len(errors) == 0


def test_lint_prompt_missing_format():
    prompt = "Read this text and tell me what you think about it."
    findings = lint_prompt(prompt)
    codes = [f["code"] for f in findings]
    assert "missing_format" in codes


def test_lint_prompt_contradictory():
    prompt = "Provide a concise summary of the article, but make sure it is an exhaustive, in-depth, and detailed breakdown."
    findings = lint_prompt(prompt)
    codes = [f["code"] for f in findings]
    assert "contradictory" in codes


def test_lint_prompt_vague():
    prompt = "Write an appropriate response using reasonable guidelines and include etc. as needed."
    findings = lint_prompt(prompt)
    codes = [f["code"] for f in findings]
    assert "vague" in codes


def test_lint_prompt_multi_task():
    prompt = "Please summarize this document, translate it to French, write SQL to query the results, and analyze sentiment."
    findings = lint_prompt(prompt)
    codes = [f["code"] for f in findings]
    assert "multi_task" in codes


def test_lint_prompt_no_refusal():
    prompt = "Extract numbers into a JSON array: [1, 2, 3]."
    findings = lint_prompt(prompt)
    codes = [f["code"] for f in findings]
    assert "no_refusal" in codes


def test_lint_prompt_injection_prone():
    prompt = "Here is the raw text: {user_input}. Process it."
    findings = lint_prompt(prompt)
    codes = [f["code"] for f in findings]
    assert "injection_prone" in codes


def test_lint_prompt_personal_data():
    prompt = "Collect user records and prompt them for their ssn and passwords to verify identity."
    findings = lint_prompt(prompt)
    codes = [f["code"] for f in findings]
    assert "personal_data" in codes


def test_lint_skill_valid():
    valid_skill = """---
name: doc-cleaner
description: Clean and standardize raw markdown document formatting into clean typography.
version: 1.0.0
owner: agent-team
tags:
  - document
inputs:
  - raw_doc: string
outputs:
  - clean_doc: string
---

# Doc Cleaner Skill

## Trigger Conditions
- Activate when markdown documents contain trailing spaces or messy headings.

## Instructions
1. Parse document headings.
2. Standardize whitespace.
"""
    res = lint_skill(valid_skill, skill_folder_name="doc-cleaner")
    assert res["valid"] is True
    assert len(res["errors"]) == 0


def test_lint_skill_missing_fields():
    invalid_skill = """---
name: broken-skill
description: Too short
---
# Body
"""
    res = lint_skill(invalid_skill)
    assert res["valid"] is False
    assert any("missing required field" in err for err in res["errors"])


def test_lint_skill_description_length():
    short_desc = """---
name: test-skill
description: short
version: 1.0.0
owner: test
tags: [test]
inputs: [x]
outputs: [y]
---
# Body
"""
    res = lint_skill(short_desc)
    assert res["valid"] is False
    assert any("at least 20 characters" in err for err in res["errors"])

