import json
from pathlib import Path

ALLOWED_ACTIONS = {"decision", "status", "note", "handoff"}
ALLOWED_OPS = {"eq", "ne", "in", "truthy"}

def _get(ctx, key):
    cur = ctx
    for part in str(key).split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur

def _atom(atom, ctx):
    if not isinstance(atom, dict):
        return False
    op = atom.get("op", "eq")
    if op not in ALLOWED_OPS:
        return False
    actual = _get(ctx, atom.get("field"))
    expected = atom.get("value")
    if op == "eq": return actual == expected
    if op == "ne": return actual != expected
    if op == "in": return actual in (expected or [])
    if op == "truthy": return bool(actual)
    return False

def evaluate(expr, ctx):
    if not isinstance(expr, dict):
        return False
    if "ET" in expr:
        return all(evaluate(x, ctx) for x in expr["ET"])
    if "OU" in expr:
        return any(evaluate(x, ctx) for x in expr["OU"])
    if "SI" in expr:
        return evaluate(expr["SI"], ctx)
    return _atom(expr, ctx)

def run_rules(rules, ctx):
    out = []
    for rule in rules.get("rules", []):
        if not evaluate(rule.get("SI", {}), ctx):
            continue
        actions = rule.get("ALORS", [])
        if isinstance(actions, dict):
            actions = [actions]
        for action in actions:
            kind = action.get("action")
            if kind not in ALLOWED_ACTIONS:
                continue
            payload = {k:v for k,v in action.items() if k != "action"}
            out.append({"action": kind, **payload})
    return out

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
