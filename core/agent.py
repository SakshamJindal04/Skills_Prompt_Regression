"""
Local Deterministic Tool-Using Agent and Trajectory Execution Engine.
Provides:
1. Three deterministic local tools:
   - `calculator`: Safe mathematical evaluator.
   - `doc_lookup`: Safe read-only document search in data/sample_docs/.
   - `db_query`: Safe read-only SQLite query on data/sample_agent.db.
2. Agent execution loop capturing step-by-step trajectories in JSON format.
3. Invariant checks: right tool, valid arguments, step count, loop detection, final answer correctness.
"""

import ast
import json
import math
import operator
import re
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from core.llm import default_client, OllamaClient

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "sample_docs"
DB_PATH = BASE_DIR / "data" / "sample_agent.db"

# Safe mathematical evaluation operators
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}

_SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
}


def _eval_ast_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value}")
    elif isinstance(node, ast.BinOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if not op_func:
            raise ValueError(f"Unsupported operator: {type(node.op)}")
        left = _eval_ast_node(node.left)
        right = _eval_ast_node(node.right)
        return op_func(left, right)
    elif isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if not op_func:
            raise ValueError(f"Unsupported unary operator: {type(node.op)}")
        return op_func(_eval_ast_node(node.operand))
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
            func = _SAFE_FUNCTIONS[node.func.id]
            args = [_eval_ast_node(arg) for arg in node.args]
            return func(*args)
        raise ValueError(f"Unsupported function call in expression: {node.func}")
    else:
        raise ValueError(f"Unsupported expression construct: {type(node)}")


# --- Tool 1: Calculator ---
def tool_calculator(expression: str) -> str:
    """Safely evaluates arithmetic expressions without eval() or shell execution."""
    expr_clean = str(expression or "").strip()
    if not expr_clean:
        return "ERROR: Empty expression."
    try:
        parsed = ast.parse(expr_clean, mode="eval")
        result = _eval_ast_node(parsed.body)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return str(result)
    except Exception as e:
        return f"ERROR: Failed to evaluate expression '{expr_clean}': {e}"


# --- Tool 2: Document Lookup ---
def tool_doc_lookup(query: str, doc_name: Optional[str] = None) -> str:
    """Searches sample enterprise documents in data/sample_docs/ for keywords."""
    if not DOCS_DIR.exists():
        return "ERROR: Documentation directory not found."

    q_lower = str(query or "").strip().lower()
    if not q_lower:
        return "ERROR: Empty search query."

    files_to_check = []
    if doc_name:
        clean_name = Path(doc_name).name
        target_f = DOCS_DIR / clean_name
        if target_f.exists() and target_f.is_file():
            files_to_check.append(target_f)
        else:
            return f"ERROR: Document '{doc_name}' not found."
    else:
        files_to_check = list(DOCS_DIR.glob("*.txt"))

    matches = []
    for f in sorted(files_to_check):
        content = f.read_text(encoding="utf-8")
        lines = content.split("\n")
        matching_lines = [line.strip() for line in lines if q_lower in line.lower() and line.strip()]
        if matching_lines:
            matches.append(f"[{f.name}]\n" + "\n".join(matching_lines[:4]))

    if matches:
        return "\n\n".join(matches)
    return f"No matches found for '{query}' in documented policies."


# --- Tool 3: SQLite Query ---
def tool_db_query(sql: str) -> str:
    """Executes strictly read-only SELECT queries on sample_agent.db."""
    if not DB_PATH.exists():
        return "ERROR: Database file not found."

    clean_sql = str(sql or "").strip()
    if not clean_sql:
        return "ERROR: Empty SQL query."

    # Enforce read-only constraint
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE", "REPLACE", "EXEC", "PRAGMA"]
    upper_sql = clean_sql.upper()
    for kw in forbidden:
        if re.search(r"\b" + kw + r"\b", upper_sql):
            return f"ERROR: Write operation '{kw}' is prohibited. Only read-only SELECT queries are allowed."

    if not upper_sql.startswith("SELECT") and not upper_sql.startswith("WITH"):
        return "ERROR: Only SELECT queries are permitted."

    try:
        conn = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(clean_sql)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()

        if not rows:
            return "No rows returned."

        # Format output as compact tabular text
        header = " | ".join(col_names)
        divider = "-+-".join(["-" * len(c) for c in col_names])
        row_lines = [" | ".join(str(val) for val in r) for r in rows[:10]]
        return f"{header}\n{divider}\n" + "\n".join(row_lines)
    except Exception as e:
        return f"ERROR: SQL execution failed: {e}"


TOOL_DISPATCHER = {
    "calculator": lambda args: tool_calculator(args.get("expression", args.get("expr", ""))),
    "doc_lookup": lambda args: tool_doc_lookup(args.get("query", ""), doc_name=args.get("doc_name")),
    "db_query": lambda args: tool_db_query(args.get("sql", args.get("query", ""))),
}

AGENT_SYSTEM_PROMPT = """You are a deterministic local enterprise assistant with access to three local tools:

1. `calculator`: Evaluates arithmetic expressions. Args: {"expression": "..."}
2. `doc_lookup`: Searches local company docs (sla_policy.txt, server_specs.txt, pricing_tiers.txt, security_guidelines.txt). Args: {"query": "...", "doc_name": "..." (optional)}
3. `db_query`: Runs read-only SELECT SQL queries on the database (tables: inventory, employees, orders). Args: {"sql": "..."}

You MUST emit ONLY a single valid JSON action on every turn. Format:
{"thought": "reasoning step", "action": "tool_name", "args": {"arg_key": "arg_value"}}

When you have sufficient information to answer the question, emit:
{"thought": "reasoning step", "action": "final_answer", "answer": "your exact concise answer"}

Rules:
- Do not make up facts. Lookup data using the appropriate tool.
- Output ONLY the raw JSON object. No markdown backticks, no explanations outside the JSON."""


def parse_action_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Extracts JSON action dictionary from model output."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Search for first { ... }
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    try:
        return json.loads(cleaned)
    except Exception:
        return None


def run_agent_trajectory(
    task_input: str,
    client: Optional[OllamaClient] = None,
    model: str = "qwen2.5:3b",
    max_steps: int = 5,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes an agent trajectory with tool usage, loop detection, and structured trace recording.
    """
    llm = client or default_client
    sys_prompt = system_prompt or AGENT_SYSTEM_PROMPT

    trajectory: List[Dict[str, Any]] = []
    seen_actions: List[str] = []
    tools_used: List[str] = []
    loop_detected = False
    step_limit_exceeded = False
    final_answer = ""

    conversation = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": task_input},
    ]

    for step in range(1, max_steps + 1):
        prompt_full = "\n\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in conversation]) + "\n\nASSISTANT:"

        # Generate action with local model
        resp = llm.generate(
            prompt=prompt_full,
            model=model,
            temperature=0.0,
            seed=42 + step,
        )

        raw_resp = resp.text.strip()
        action_dict = parse_action_json(raw_resp)

        if not action_dict or not isinstance(action_dict, dict):
            # Parse error: try to recover or treat as final answer
            trajectory.append({
                "step": step,
                "thought": "Failed to parse structured JSON action.",
                "action": "parse_error",
                "args": {},
                "raw_response": raw_resp,
                "observation": "ERROR: Invalid JSON action emitted.",
                "latency_ms": resp.latency_ms,
            })
            final_answer = raw_resp
            break

        action = action_dict.get("action", "")
        args = action_dict.get("args", {})
        thought = action_dict.get("thought", "")

        # Check for final answer
        if action == "final_answer":
            final_answer = str(action_dict.get("answer", raw_resp))
            trajectory.append({
                "step": step,
                "thought": thought,
                "action": "final_answer",
                "args": {"answer": final_answer},
                "observation": "COMPLETED",
                "latency_ms": resp.latency_ms,
            })
            break

        # Check for loop: identical action and args repeated
        action_key = f"{action}:{json.dumps(args, sort_keys=True)}"
        if action_key in seen_actions:
            loop_detected = True
            trajectory.append({
                "step": step,
                "thought": thought,
                "action": action,
                "args": args,
                "observation": "ERROR: Infinite loop detected: identical action and arguments called repeatedly.",
                "latency_ms": resp.latency_ms,
            })
            final_answer = f"TERMINATED: Infinite loop in tool '{action}'."
            break

        seen_actions.append(action_key)
        tools_used.append(action)

        # Dispatch tool
        handler = TOOL_DISPATCHER.get(action)
        if handler:
            try:
                observation = handler(args)
            except Exception as e:
                observation = f"ERROR executing tool '{action}': {e}"
        else:
            observation = f"ERROR: Unknown tool '{action}'. Valid tools are: {list(TOOL_DISPATCHER.keys())}"

        trajectory.append({
            "step": step,
            "thought": thought,
            "action": action,
            "args": args,
            "observation": observation,
            "latency_ms": resp.latency_ms,
        })

        # Append observation to conversation for next turn
        conversation.append({"role": "assistant", "content": raw_resp})
        conversation.append({"role": "user", "content": f"Observation from {action}:\n{observation}"})

    else:
        # Loop exhausted max_steps without final_answer
        step_limit_exceeded = True
        if not final_answer:
            final_answer = "TERMINATED: Step limit exceeded without final answer."

    return {
        "task_input": task_input,
        "final_answer": final_answer,
        "trajectory": trajectory,
        "step_count": len(trajectory),
        "loop_detected": loop_detected,
        "step_limit_exceeded": step_limit_exceeded,
        "tools_used": sorted(list(set(tools_used))),
    }
