#!/usr/bin/env python3
"""Record internal/gateway/testdata/policy.json: the tier policy and table row of
examples/29_presets_model_router.py on synthetic answers, with the example's own formatting.

    python laya-go/samples/scripts/gen_router_policy_golden.py          # write
    python laya-go/samples/scripts/gen_router_policy_golden.py --check  # fail if the file differs
"""
import argparse
import json
import pathlib
import sys

OUT = pathlib.Path(__file__).resolve().parents[1] / "internal" / "gateway" / "testdata" / "policy.json"


# Copied from examples/29_presets_model_router.py.
def route_tier(answers):
    difficulty = answers["difficulty"]["score"]
    sensitive = answers["is_sensitive"]["noul"]
    tools = answers["needs_tools"]["noul"]
    if sensitive >= 0.5:
        return "frontier", "sensitive: money/legal/medical/safety (p=%.2f)" % sensitive
    if tools >= 0.5:
        return "frontier+tools", "needs external data (p=%.2f)" % tools
    if difficulty >= 1.5:
        return "frontier", "difficulty %.2f >= 1.5" % difficulty
    return "small", "difficulty %.2f < 1.5, no tools, not sensitive" % difficulty


def row(label, a):
    domain = max(a["domain"]["probabilities"].items(), key=lambda kv: kv[1])
    return "   %-17s %.2f / 3   %-16s %-11.3f %.3f" % (
        label, a["difficulty"]["score"], "%s (%.2f)" % (domain[0], domain[1]),
        a["needs_tools"]["noul"], a["is_sensitive"]["noul"])


def case(d, probs, tools, sens):
    return {"difficulty": {"score": d}, "domain": {"probabilities": probs},
            "needs_tools": {"noul": tools}, "is_sensitive": {"noul": sens}}


DOMAINS = {"code": 0.1, "math_or_logic": 0.2, "writing": 0.3, "factual_lookup": 0.3, "data_analysis": 0.05,
           "chitchat": 0.05}
CASES = [
    ("small", case(0.4, DOMAINS, 0.1, 0.1)),
    ("hard", case(2.2, DOMAINS, 0.2, 0.3)),
    ("at-difficulty-threshold", case(1.5, DOMAINS, 0.2, 0.3)),
    ("just-under-threshold", case(1.4999, DOMAINS, 0.2, 0.3)),
    ("tools", case(0.2, DOMAINS, 0.5, 0.49)),
    ("sensitive-overrides-tools", case(0.2, DOMAINS, 0.9, 0.5)),
    ("sensitive-easy", case(0.1, DOMAINS, 0.0, 0.97)),
]


def render():
    out = []
    for name, a in CASES:
        tier, why = route_tier(a)
        out.append({"name": name, "difficulty": a["difficulty"]["score"], "domains": a["domain"]["probabilities"],
                    "needs_tools": a["needs_tools"]["noul"], "is_sensitive": a["is_sensitive"]["noul"],
                    "tier": tier, "why": why, "row": row("label", a)})
    return json.dumps(out, ensure_ascii=False, indent=1) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("%s differs" % OUT)
            return 1
        print("%s matches" % OUT)
        return 0
    OUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
