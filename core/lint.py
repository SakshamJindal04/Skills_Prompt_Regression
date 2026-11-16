import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional

VAGUE_TERMS = [
    r"\betc\.?\b",
    r"\band so on\b",
    r"\bappropriate\b",
    r"\breasonable\b",
    r"\bas needed\b",
    r"\bgood quality\b",
    r"\bas appropriate\b",
    r"\bsuitable\b"
]

FORMAT_INDICATORS = [
    r"\bjson\b",
    r"\bmarkdown\b",
    r"\btable\b",
    r"\bbullet\b",
    r"\bcsv\b",
    r"\bschema\b",
    r"\bxml\b",
    r"\bformat\b",
    r"\byaml\b",
    r"\blist\b"
]

REFUSAL_INDICATORS = [
    r"\brefuse\b",
    r"\bdecline\b",
    r"\bif unable\b",
    r"\bdo not\b",
    r"\bout of scope\b",
    r"\bnot applicable\b",
    r"\bfallback\b",
    r"\bcannot answer\b",
    r"\bif missing\b",
    r"\breject\b"
]

PII_PATTERNS = [
    r"\bssn\b",
    r"\bsocial security\b",
    r"\bcredit card\b",
    r"\bpassport number\b",
    r"\bpasswords?\b",
    r"\bdate of birth\b",
    r"\bpin code\b",
    r"\bcvv\b"
]

TASK_VERBS = [
    r"\bsummariz(e|ation)\b",
    r"\btranslat(e|ion)\b",
    r"\bclassif(y|ication)\b",
    r"\bextract(ion)?\b",
    r"\bgenerat(e|ion) sql\b",
    r"\banalyz(e|is) sentiment\b",
    r"\bwrite code\b"
]


def lint_prompt(text: str) -> List[Dict[str, Any]]:
    """
    Statically lints a prompt text against quality, safety, and formatting rules.
    Returns a list of findings:
    [
        {"code": "...", "severity": "error"|"warning", "message": "...", "line": int}
    ]
    """
    findings = []
    if not text or not text.strip():
        findings.append({
            "code": "empty_prompt",
            "severity": "error",
            "message": "Prompt content is empty.",
            "line": 1
        })
        return findings

    lines = text.split("\n")
    lower_text = text.lower()

    # 1. missing_format (warning/error)
    has_format = any(re.search(pat, lower_text) for pat in FORMAT_INDICATORS)
    if not has_format:
        findings.append({
            "code": "missing_format",
            "severity": "warning",
            "message": "No explicit output format specified (e.g. JSON, Markdown, table, bullets).",
            "line": 1
        })

    # 2. vague (warning)
    for i, line in enumerate(lines, 1):
        for term in VAGUE_TERMS:
            m = re.search(term, line, re.IGNORECASE)
            if m:
                findings.append({
                    "code": "vague",
                    "severity": "warning",
                    "message": f"Vague phrase '{m.group(0)}' used without concrete operational definition.",
                    "line": i
                })

    # 3. contradictory directives
    has_concise = bool(re.search(r"\b(concise|brief|short|terse)\b", lower_text))
    has_detailed = bool(re.search(r"\b(detailed|exhaustive|comprehensive|in-depth)\b", lower_text))
    if has_concise and has_detailed:
        findings.append({
            "code": "contradictory",
            "severity": "error",
            "message": "Contradictory directives detected: prompt requests both brevity/conciseness and detailed/exhaustive output.",
            "line": 1
        })

    # 4. multi_task (warning)
    detected_tasks = []
    for tv in TASK_VERBS:
        if re.search(tv, lower_text):
            detected_tasks.append(tv)
    if len(detected_tasks) >= 3:
        findings.append({
            "code": "multi_task",
            "severity": "warning",
            "message": f"Prompt appears to cram {len(detected_tasks)} distinct tasks into one prompt.",
            "line": 1
        })

    # 5. no_refusal (warning)
    has_refusal = any(re.search(pat, lower_text) for pat in REFUSAL_INDICATORS)
    if not has_refusal:
        findings.append({
            "code": "no_refusal",
            "severity": "warning",
            "message": "No negative guidance or refusal instructions for handling out-of-scope or invalid inputs.",
            "line": 1
        })

    # 6. injection_prone (error/warning)
    # Check for variables like {input} or {text} that are NOT surrounded by quotes, backticks, or delimiters
    raw_var_matches = re.finditer(r"(?<![\"\'`<\$])\{([a-zA-Z0-9_]+)\}(?![\"\'`>])", text)
    for m in raw_var_matches:
        var_name = m.group(1)
        # Find line number
        start_pos = m.start()
        line_num = text[:start_pos].count("\n") + 1
        findings.append({
            "code": "injection_prone",
            "severity": "warning",
            "message": f"Template variable '{{{var_name}}}' is interpolated without delimiters, quotes, or markdown code blocks, making it susceptible to injection.",
            "line": line_num
        })

    # 7. personal_data (error)
    for i, line in enumerate(lines, 1):
        for pii in PII_PATTERNS:
            m = re.search(pii, line, re.IGNORECASE)
            if m:
                findings.append({
                    "code": "personal_data",
                    "severity": "error",
                    "message": f"Potential personal identifier / sensitive data request detected: '{m.group(0)}'.",
                    "line": i
                })

    return findings


def parse_skill_markdown(content: str) -> tuple[Optional[Dict[str, Any]], str]:
    """
    Parses frontmatter YAML and markdown body from SKILL.md content.
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content.strip(), re.DOTALL)
    if not match:
        return None, content

    yaml_block = match.group(1)
    body = match.group(2)
    try:
        data = yaml.safe_load(yaml_block)
        return data if isinstance(data, dict) else None, body
    except Exception:
        return None, body


def lint_skill(skill_path_or_text: str, skill_folder_name: Optional[str] = None, existing_skills: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Lints a SKILL.md file or string.
    Checks:
      - Valid YAML frontmatter with: name, description, version, owner, tags, inputs, outputs
      - name matches lowercase-hyphenated pattern and matches folder name (if given)
      - description length between 20 and 250 characters
      - instructions / triggers non-empty
      - overlap with existing skills <= 0.85 cosine similarity
    """
    findings = []
    content = ""
    folder_name = skill_folder_name

    if "\n" not in skill_path_or_text and len(skill_path_or_text) < 260:
        p = Path(skill_path_or_text)
        if p.exists() and p.is_file():
            content = p.read_text(encoding="utf-8")
            if not folder_name:
                folder_name = p.parent.name
        else:
            content = skill_path_or_text
    else:
        content = skill_path_or_text

    frontmatter, body = parse_skill_markdown(content)
    if frontmatter is None:
        findings.append({
            "code": "invalid_frontmatter",
            "severity": "error",
            "message": "SKILL.md must begin with a valid YAML frontmatter block enclosed by '---'."
        })
        return {
            "valid": False,
            "errors": [f["message"] for f in findings if f["severity"] == "error"],
            "warnings": [f["message"] for f in findings if f["severity"] == "warning"],
            "findings": findings,
            "metadata": {}
        }

    # Required fields
    required_fields = ["name", "description", "version", "owner", "tags", "inputs", "outputs"]
    for req in required_fields:
        if req not in frontmatter or frontmatter[req] is None or frontmatter[req] == "":
            findings.append({
                "code": f"missing_{req}",
                "severity": "error",
                "message": f"Frontmatter is missing required field '{req}'."
            })

    # Validate name format
    name = str(frontmatter.get("name", ""))
    if name:
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
            findings.append({
                "code": "invalid_name_format",
                "severity": "error",
                "message": f"Skill name '{name}' must be lowercase alphanumeric with hyphens (e.g. 'text-summarizer')."
            })
        if folder_name and folder_name != "skills" and name != folder_name:
            findings.append({
                "code": "name_folder_mismatch",
                "severity": "error",
                "message": f"Skill name '{name}' does not match enclosing folder name '{folder_name}'."
            })

    # Validate description length
    desc = str(frontmatter.get("description", ""))
    if desc:
        if len(desc) < 20:
            findings.append({
                "code": "description_too_short",
                "severity": "error",
                "message": f"Description must be at least 20 characters (current: {len(desc)})."
            })
        elif len(desc) > 250:
            findings.append({
                "code": "description_too_long",
                "severity": "error",
                "message": f"Description must be at most 250 characters (current: {len(desc)})."
            })

    # Validate body / steps
    if not body.strip():
        findings.append({
            "code": "empty_instructions",
            "severity": "error",
            "message": "Skill body contains no instructions, steps, or prompt guidance."
        })

    # Overlap check with existing skills if provided
    if existing_skills and name and desc:
        from core.skills import compute_text_similarity
        for other in existing_skills:
            other_name = other.get("name", "")
            if other_name == name:
                continue
            other_text = f"{other.get('name', '')} {other.get('description', '')}"
            curr_text = f"{name} {desc}"
            sim = compute_text_similarity(curr_text, other_text)
            if sim > 0.85:
                findings.append({
                    "code": "high_overlap",
                    "severity": "error",
                    "message": f"Skill has severe conceptual overlap ({sim:.2f} > 0.85) with existing skill '{other_name}'."
                })
            elif sim > 0.75:
                findings.append({
                    "code": "moderate_overlap",
                    "severity": "warning",
                    "message": f"Skill has moderate conceptual overlap ({sim:.2f} > 0.75) with existing skill '{other_name}'."
                })

    errors = [f["message"] for f in findings if f["severity"] == "error"]
    warnings = [f["message"] for f in findings if f["severity"] == "warning"]

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "metadata": frontmatter
    }
