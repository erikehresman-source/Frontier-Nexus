#!/usr/bin/env python3
import json, sys, re, pathlib

# Keywords that trigger skill-based outcomes
SKILL_RX = re.compile(r"\b(Negotiation|Deception|Combat|Survey|Pilot|Engineering)\b", re.I)

REQUIRED_KEYS = ["id","title","zone","type","faction","xpBucket","intro","choices","outro"]

def fail(msg):
    print("ERROR:", msg)
    sys.exit(2)

def warn(msg):
    print("WARN:", msg)

def pct(n, d): 
    return 0 if d==0 else (100.0*n/d)

def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_encounters.py <encounters.json> [--allow-sandbox]")
        sys.exit(1)

    allow_sandbox = "--allow-sandbox" in sys.argv
    path = sys.argv[1]
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

    if not isinstance(data, list): fail("Top-level must be a list of encounters.")
    ids = set()
    emotion = {"tension":0,"relief":0,"humor":0,"discovery":0,"":0}
    succ_cnt = fail_cnt = neut_cnt = 0

    for e in data:
        # required keys
        for k in REQUIRED_KEYS:
            if k not in e: fail(f"{e.get('id','<unknown>')}: missing key '{k}'")

        # unique ids
        if e["id"] in ids: fail(f"Duplicate id '{e['id']}'")
        ids.add(e["id"])

        # emotion tag count
        etag = (e.get("emotionTag") or "").lower()
        if etag in emotion: emotion[etag] += 1

        # choices
        for ch in e["choices"]:
            outs = ch.get("outcomes",[])
            if SKILL_RX.search(ch["text"]):
                if len(outs) != 2:
                    fail(f"{e['id']}: skill choice must have 2 outcomes (success+failure): {ch['text']}")
                kinds = [o.get("result") for o in outs]
                if "success" not in kinds or "failure" not in kinds:
                    fail(f"{e['id']}: missing success/failure outcome: {ch['text']}")
                succ = next(o for o in outs if o["result"]=="success")
                failo = next(o for o in outs if o["result"]=="failure")
                if failo.get("xp",0) >= succ.get("xp",0):
                    fail(f"{e['id']}: failure XP must be lower than success XP: {ch['text']}")
                ratio = (failo.get("xp",0)+1e-9) / (succ.get("xp",1)+1e-9)
                if ratio < 0.5 or ratio > 0.7:
                    warn(f"{e['id']}: failure XP ratio {ratio:.2f} outside 0.50-0.70: {ch['text']}")
                succ_cnt += 1; fail_cnt += 1
            else:
                if len(outs) != 1:
                    fail(f"{e['id']}: deterministic choice must have exactly 1 outcome: {ch['text']}")
                o = outs[0]
                if o.get("result") != "neutral":
                    fail(f"{e['id']}: deterministic outcome must be neutral: {ch['text']}")
                if "conditions" in o or ("rep" in o and any(v<0 for v in o["rep"].values())):
                    fail(f"{e['id']}: neutral outcome must not apply penalties: {ch['text']}")
                neut_cnt += 1

        if e.get("sandboxOutcome") and not allow_sandbox:
            warn(f"{e['id']}: sandboxOutcome present (ignored unless --allow-sandbox).")

    # Emotion pacing
    tagged_total = sum(v for k,v in emotion.items() if k)
    if tagged_total > 0:
        for k in ["tension","relief","humor","discovery"]:
            p = pct(emotion[k], tagged_total)
            if p < 15 or p > 35:
                warn(f"Emotion tag '{k}' at {p:.1f}% outside target 25%±10% (count={emotion[k]}/{tagged_total}).")

    print("OK: validation complete.")
    print("Encounters:", len(data), "| Success/Failure choices:", succ_cnt, "| Neutral choices:", neut_cnt)

if __name__ == "__main__":
    main()
