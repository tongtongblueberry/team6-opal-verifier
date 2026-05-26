# Changed: large-scale spec-based training data (target 3000+).
# Why: 382 cases was insufficient. Need diverse combinations per rule.
# Split: 60/20/20 random (not by rule). Public seed inclusion is opt-in only.

from __future__ import annotations
import argparse, json, os, sys, itertools, random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Changed: spec datagen 산출물 기본 루트를 env로 재정의 가능하게 분리.
# Why: 기본 실행이 이전 /workspace/team6/training_data에 쓰지 않도록 함.
DEFAULT_RUNTIME_ROOT = Path(
    os.environ.get("OPAL_RUNTIME_ROOT", "/workspace/sinjeongmin_opal_verifier")
)
DEFAULT_TRAINING_DATA_DIR = DEFAULT_RUNTIME_ROOT / "training_data"

Json = dict[str, Any]
random.seed(42)

# ═══════════════════════════════════════════════════════════════
# POOLS — maximized for combinatorial diversity
# ═══════════════════════════════════════════════════════════════

OBJECTS_KNOWN = [
    ("C_PIN_MSID",       "00 00 00 0B 00 00 84 02", "cpin"),
    ("C_PIN_SID",        "00 00 00 0B 00 00 00 01", "cpin"),
    ("C_PIN_Admin1",     "00 00 00 0B 00 01 00 01", "cpin"),
    ("C_PIN_Admin2",     "00 00 00 0B 00 01 00 02", "cpin"),
    ("C_PIN_User1",      "00 00 00 0B 00 03 00 01", "cpin"),
    ("C_PIN_User2",      "00 00 00 0B 00 03 00 02", "cpin"),
    ("Authority_SID",    "00 00 00 09 00 00 00 06", "authority"),
    ("Authority_Admin1", "00 00 00 09 00 01 00 01", "authority"),
    ("Authority_Admin2", "00 00 00 09 00 01 00 02", "authority"),
    ("Authority_User1",  "00 00 00 09 00 03 00 01", "authority"),
    ("Authority_User2",  "00 00 00 09 00 03 00 02", "authority"),
    ("Locking_GR",       "00 00 08 02 00 00 00 01", "locking"),
    ("Locking_Range1",   "00 00 08 02 00 03 00 01", "locking"),
    ("Locking_Range2",   "00 00 08 02 00 03 00 02", "locking"),
    ("MBRControl",       "00 00 08 03 00 00 00 01", "mbrcontrol"),
]

OBJECTS_UNKNOWN = [
    ("K_AES_256",        "00 00 08 06 00 03 00 01", "key"),
    ("K_AES_128",        "00 00 08 06 00 02 00 01", "key"),
    ("K_AES_256_R1",     "00 00 08 06 00 03 00 02", "key"),
    ("SP_Locking",       "00 00 02 05 00 00 00 01", "sp"),
    ("SP_Admin",         "00 00 02 05 00 00 00 02", "sp"),
    ("SPInfo",           "00 00 02 05 00 00 00 03", "sp"),
    ("ACE",              "00 00 00 08 00 00 00 01", "ace"),
    ("ACE_Locking_GR",   "00 00 00 08 00 03 E0 01", "ace"),
    ("Template",         "00 00 00 02 00 00 00 01", "template"),
    ("DataStore",        "00 00 10 01 00 00 00 00", "datastore"),
    ("MethodID",         "00 00 00 06 00 00 00 01", "methodid"),
    ("Table",            "00 00 00 01 00 00 00 01", "table"),
    ("SecretProtect",    "00 00 00 04 00 00 00 01", "secretprotect"),
    ("Log",              "00 00 0F 01 00 00 00 01", "log"),
    ("LogList",          "00 00 0F 02 00 00 00 01", "loglist"),
]

CLASS_AUTHORITIES = [
    ("Admins", "00 00 00 09 00 00 00 02"),
    ("Makers", "00 00 00 09 00 00 00 03"),
    ("Users",  "00 00 00 09 00 03 00 00"),
]

INDIV_AUTHORITIES = [
    ("SID",    "00 00 00 09 00 00 00 06"),
    ("Admin1", "00 00 00 09 00 01 00 01"),
    ("Admin2", "00 00 00 09 00 01 00 02"),
    ("Admin3", "00 00 00 09 00 01 00 03"),
    ("User1",  "00 00 00 09 00 03 00 01"),
    ("User2",  "00 00 00 09 00 03 00 02"),
    ("User3",  "00 00 00 09 00 03 00 03"),
]

ERRORS = ["NOT_AUTHORIZED", "INVALID_PARAMETER", "FAIL"]
COL_RANGES = ["0-3", "3-3", "3-8", "5-5", "1-2", "0-0", "0-5", "1-6"]
LBAS = ["0 ~ 7", "80 ~ 87", "100 ~ 107", "200 ~ 207", "500 ~ 507",
        "1000 ~ 1007", "1500 ~ 1507", "2000 ~ 2007"]
SPIDS = ["0000020500000001", "0000020500000002", "0000000100000001"]

# ═══════════════════════════════════════════════════════════════
# STEP BUILDERS
# ═══════════════════════════════════════════════════════════════

def _ss(write=True, auth=True, auth_uid="00 00 00 09 00 01 00 01",
        challenge="correct_password", spid="0000020500000001", status="SUCCESS"):
    args = {"required": {"HostSessionID": 1, "SPID": spid, "Write": 1 if write else 0}, "optional": {}}
    if auth:
        args["optional"]["HostSigningAuthority"] = auth_uid
        args["optional"]["HostChallenge"] = challenge
    out: Json = {"status_codes": status, "return_values": []}
    if status == "SUCCESS":
        out["method"] = {"name": "SyncSession"}
        out["return_values"] = {"required": {"HostSessionID": "00000001", "SPSessionID": "00001001"}}
    return {"input": {"method": {"name": "StartSession", "uid": "00 00 00 00 00 00 FF 02",
            "args": args}, "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "Session Manager UID"}},
            "output": out}

def _m(method, name, uid, status, cols="", vals=None, rv=None):
    req: dict = {}
    if method == "Get" and cols:
        p = cols.split("-")
        req["Cellblock"] = [{"startColumn": int(p[0])}, {"endColumn": int(p[-1])}]
    if method == "Set":
        req["Values"] = [vals or {"3": "new_value"}]
    if rv is None:
        rv = [] if status != "SUCCESS" else ([{"3": "val"}] if method == "Get" else [])
    return {"input": {"method": {"name": method}, "invoking_id": {"uid": uid, "name": name},
            "args": {"required": req, "optional": {}}}, "output": {"return_values": rv, "status_codes": status}}

def _auth(name, uid, status="SUCCESS", result=True):
    return {"input": {"method": {"name": "Authenticate"}, "invoking_id": {"uid": uid, "name": name},
            "args": {"required": {}, "optional": {"Proof": "cred"}}},
            "output": {"return_values": [result], "status_codes": status}}

def _data(cmd, lba, status, payload="", result=""):
    inp: Json = {"command": cmd, "args": {"LBA": lba}}
    if cmd == "Write" and payload: inp["args"]["pattern"] = payload
    out: Json = {"command": cmd, "status_codes": status}
    if cmd == "Read" and result: out["args"] = {"result": result}
    return {"input": inp, "output": out}

# ═══════════════════════════════════════════════════════════════
# GENERATORS — maximized combinations
# ═══════════════════════════════════════════════════════════════

def gen_all() -> list[dict]:
    C: list[dict] = []
    def add(steps, label, rule, desc):
        C.append({"steps": steps, "label": label, "spec_rule": rule, "description": desc})

    ALL = OBJECTS_KNOWN + OBJECTS_UNKNOWN

    # ── R1: No session + method → error expected (5.2.2.3) ──
    for m in ["Get", "Set"]:
        for n, u, _ in ALL:
            for e in ERRORS:
                add([_m(m, n, u, e, cols="3-3")], "pass", "5.2.2.3", f"nosess+{m}({n})->{e}")
            add([_m(m, n, u, "SUCCESS", cols="3-3")], "fail", "5.2.2.3", f"nosess+{m}({n})->SUCCESS")

    # ── R2: Unauth + write → NOT_AUTHORIZED (3.3.7.1) ──
    for m in ["Set", "GenKey", "Activate"]:
        for n, u, _ in ALL:
            add([_ss(auth=False), _m(m, n, u, "NOT_AUTHORIZED")], "pass", "3.3.7.1", f"unauth+{m}({n})->NA")
            add([_ss(auth=False), _m(m, n, u, "SUCCESS")], "fail", "3.3.7.1", f"unauth+{m}({n})->OK")

    # ── R3: Class auth in StartSession → INVALID_PARAMETER (5.1.5.11) ──
    for an, au in CLASS_AUTHORITIES:
        for spid in SPIDS:
            add([_ss(auth=True, auth_uid=au, spid=spid, status="INVALID_PARAMETER")],
                "pass", "5.1.5.11", f"SS({an},{spid})->IP")
            add([_ss(auth=True, auth_uid=au, spid=spid, status="SUCCESS")],
                "fail", "5.1.5.11", f"SS({an},{spid})->OK")
            add([_ss(auth=True, auth_uid=au, spid=spid, status="NOT_AUTHORIZED")],
                "fail", "5.1.5.11-wrongerr", f"SS({an},{spid})->NA")

    # ── R4: Wrong password → NOT_AUTHORIZED (5.1.5.2) ──
    for an, au in INDIV_AUTHORITIES:
        for pw in ["wrong1", "wrong2", "empty", "12345"]:
            add([_ss(auth=True, auth_uid=au, challenge=pw, status="NOT_AUTHORIZED")],
                "pass", "5.1.5.2", f"SS({an},pw={pw})->NA")
            add([_ss(auth=True, auth_uid=au, challenge=pw, status="SUCCESS")],
                "fail", "5.1.5.2", f"SS({an},pw={pw})->OK")

    # ── R5: Correct auth → SUCCESS (5.1.5.1) ──
    for an, au in INDIV_AUTHORITIES:
        add([_ss(auth=True, auth_uid=au, status="SUCCESS")],
            "pass", "5.1.5.1", f"SS({an},correct)->OK")
        add([_ss(auth=True, auth_uid=au, status="NOT_AUTHORIZED")],
            "fail", "5.1.5.1", f"SS({an},correct)->NA")

    # ── R6: Properties (5.2.3) ──
    props_ok = {"input": {"method": {"name": "Properties"}, "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "SM"}},
                "output": {"return_values": [{"Properties": {"MaxMethods": 1}}], "status_codes": "SUCCESS"}}
    props_bad = {"input": {"method": {"name": "Properties"}, "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "SM"}},
                 "output": {"return_values": [], "status_codes": "SUCCESS"}}
    add([props_ok], "pass", "5.2.3", "Props->OK(payload)")
    add([props_bad], "fail", "5.2.3", "Props->OK(no payload)")

    # ── R7: SyncSession format (5.2.3.2) ──
    add([_ss(auth=True)], "pass", "5.2.3.2", "SS->SyncSession(ok)")
    no_sync = {"input": {"method": {"name": "StartSession", "args": {"required": {"HostSessionID":1,"SPID":"0000020500000001","Write":1},
               "optional":{"HostSigningAuthority":"00 00 00 09 00 01 00 01","HostChallenge":"pw"}}},
               "invoking_id": {"uid": "00 00 00 00 00 00 00 FF", "name": "SM"}},
               "output": {"status_codes": "SUCCESS", "return_values": []}}
    add([no_sync], "fail", "5.2.3.2", "SS->OK(no sync)")

    # ── R8: Set/GenKey SUCCESS = empty result (5.3.3.7) ──
    for m in ["Set", "GenKey"]:
        for n, u, _ in ALL:
            add([_ss(auth=True), _m(m, n, u, "SUCCESS", rv=[])], "pass", "5.3.3.7", f"{m}({n})->OK(empty)")
            add([_ss(auth=True), _m(m, n, u, "SUCCESS", rv=[{"x":"y"}])], "fail", "5.3.3.7", f"{m}({n})->OK(non-empty)")

    # ── R9: Invalid Cellblock (5.3.3.6) ──
    invalid_cols = ["5-3", "10-2", "8-0"]
    for ic in invalid_cols:
        for n, u, _ in ALL[:10]:
            add([_ss(auth=True), _m("Get", n, u, "INVALID_PARAMETER", cols=ic)],
                "pass", "5.3.3.6", f"Get({n},{ic})->IP")
            add([_ss(auth=True), _m("Get", n, u, "SUCCESS", cols=ic)],
                "fail", "5.3.3.6", f"Get({n},{ic})->OK")

    # ── R10: Auth + known readable → SUCCESS (5.3.4.2) ──
    readable = [("C_PIN_MSID","00 00 00 0B 00 00 84 02","3-3"),
                ("Locking_GR","00 00 08 02 00 00 00 01","3-8"),
                ("Locking_Range1","00 00 08 02 00 03 00 01","3-8"),
                ("Authority_Admin1","00 00 00 09 00 01 00 01","5-5"),
                ("Authority_User1","00 00 00 09 00 03 00 01","5-5"),
                ("MBRControl","00 00 08 03 00 00 00 01","1-2")]
    for n, u, c in readable:
        for an, au in INDIV_AUTHORITIES[:4]:
            add([_ss(auth=True, auth_uid=au), _m("Get", n, u, "SUCCESS", cols=c)],
                "pass", "5.3.4.2", f"{an}+Get({n},{c})->OK")
            for e in ERRORS:
                add([_ss(auth=True, auth_uid=au), _m("Get", n, u, e, cols=c)],
                    "fail", "5.3.4.2", f"{an}+Get({n},{c})->{e}")

    # ── R11: MSID Anybody-accessible (opal/4.2.1.5) ──
    for w in [True, False]:
        add([_ss(write=w, auth=False), _m("Get","C_PIN_MSID","00 00 00 0B 00 00 84 02","SUCCESS",cols="3-3")],
            "pass", "opal/4.2.1.5", f"unauth(w={w})+Get(MSID)->OK")
        add([_ss(write=w, auth=False), _m("Get","C_PIN_MSID","00 00 00 0B 00 00 84 02","NOT_AUTHORIZED",cols="3-3")],
            "fail", "opal/4.2.1.5", f"unauth(w={w})+Get(MSID)->NA")

    # ── R12: Authenticate class → INVALID_PARAMETER (5.3.4.1.14.1) ──
    for an, au in CLASS_AUTHORITIES:
        add([_ss(auth=True), _auth(an, au, "INVALID_PARAMETER", None)],
            "pass", "5.3.4.1.14.1-class", f"Auth({an})->IP")
        add([_ss(auth=True), _auth(an, au, "SUCCESS", True)],
            "fail", "5.3.4.1.14.1-class", f"Auth({an})->OK/T")
        add([_ss(auth=True), _auth(an, au, "SUCCESS", False)],
            "fail", "5.3.4.1.14.1-class", f"Auth({an})->OK/F")

    # ── R13: Authenticate correct → SUCCESS/True (5.3.4.1.14.1) ──
    for an, au in INDIV_AUTHORITIES:
        add([_ss(auth=True), _auth(an, au, "SUCCESS", True)],
            "pass", "5.3.4.1.14.1-ok", f"Auth({an},ok)->T")
        add([_ss(auth=True), _auth(an, au, "SUCCESS", False)],
            "fail", "5.3.4.1.14.1-ok", f"Auth({an},ok)->F")
        add([_ss(auth=True), _auth(an, au, "NOT_AUTHORIZED", None)],
            "fail", "5.3.4.1.14.1-ok", f"Auth({an},ok)->NA")

    # ── R14: Authenticate wrong → SUCCESS/False (5.3.4.1.14.1) ──
    for an, au in INDIV_AUTHORITIES:
        add([_ss(auth=True), _auth(an, au, "SUCCESS", False)],
            "pass", "5.3.4.1.14.1-wrong", f"Auth({an},wrong)->F")
        add([_ss(auth=True), _auth(an, au, "NOT_AUTHORIZED", None)],
            "fail", "5.3.4.1.14.1-wrong", f"Auth({an},wrong)->NA(should F)")

    # ── R15: Anybody → always True (5.3.4.1.2.1) ──
    add([_ss(auth=True), _auth("Anybody","00 00 00 09 00 00 00 01","SUCCESS",True)],
        "pass", "5.3.4.1.2.1", "Auth(Anybody)->T")
    add([_ss(auth=True), _auth("Anybody","00 00 00 09 00 00 00 01","SUCCESS",False)],
        "fail", "5.3.4.1.2.1", "Auth(Anybody)->F")

    # ── R16: Data consistency (Write+Read) ──
    for lba in LBAS:
        for pat in ["0xAA", "0xBB", "0xCC", "0x00", "0xFF"]:
            add([_ss(auth=True), _data("Write",lba,"Success",payload=pat), _data("Read",lba,"Success",result="data")],
                "pass", "data_consistency", f"W({lba},{pat})+R->OK")
        for e in ["FAIL", "NOT_AUTHORIZED"]:
            add([_ss(auth=True), _data("Write",lba,"Success",payload="0xDD"), _data("Read",lba,e)],
                "fail", "data_consistency", f"W({lba})+R->{e}")

    # ── R17: Read-Only + write method (3.3.7.1-RO) ──
    for m in ["Set", "GenKey", "Activate"]:
        for n, u, _ in ALL:
            add([_ss(write=False, auth=True), _m(m, n, u, "NOT_AUTHORIZED")],
                "pass", "3.3.7.1-RO", f"RO+{m}({n})->NA")
            add([_ss(write=False, auth=True), _m(m, n, u, "SUCCESS")],
                "fail", "3.3.7.1-RO", f"RO+{m}({n})->OK")

    # ── R18: Unauth + unknown object + error (valid) ──
    for n, u, _ in OBJECTS_UNKNOWN:
        for e in ERRORS:
            for c in COL_RANGES[:4]:
                add([_ss(auth=False), _m("Get", n, u, e, cols=c)],
                    "pass", "5.1.5.2-unknown", f"unauth+Get({n},{c})->{e}")

    # ── R19: Auth + unknown object + error ──
    # Changed: split by error type. NOT_AUTHORIZED on ACL-restricted objects is valid (→ pass).
    # Why: noise analysis found ~120 cases with wrong "fail" labels. ACLs restrict per-object
    # access even for authenticated authorities. Only FAIL status is genuinely wrong (→ fail).
    for n, u, _ in OBJECTS_UNKNOWN:
        for c in COL_RANGES[:4]:
            # NOT_AUTHORIZED: likely valid ACL restriction → pass
            add([_ss(auth=True), _m("Get", n, u, "NOT_AUTHORIZED", cols=c)],
                "pass", "5.3.4.2-unknown-acl", f"auth+Get({n},{c})->NA(ACL)")
            # FAIL: genuinely wrong response for authenticated access → fail
            add([_ss(auth=True), _m("Get", n, u, "FAIL", cols=c)],
                "fail", "5.3.4.2-unknown", f"auth+Get({n},{c})->FAIL")

    # ── R20: Dup cols in Set → INVALID_PARAMETER (5.3.4.2.6) ──
    for n, u, _ in ALL[:10]:
        add([_ss(auth=True), _m("Set", n, u, "INVALID_PARAMETER", vals=[{"3":"a"},{"3":"b"}])],
            "pass", "5.3.4.2.6", f"Set({n},dup)->IP")
        add([_ss(auth=True), _m("Set", n, u, "SUCCESS", vals=[{"3":"a"},{"3":"b"}])],
            "fail", "5.3.4.2.6", f"Set({n},dup)->OK")

    # ── R21: Random Count>32 (opal/4.2.9.1) ──
    for cnt in [33, 64, 100, 256]:
        rnd = lambda s, c=cnt: {"input": {"method": {"name": "Random"}, "invoking_id": {"uid": "00 00 00 00 00 00 00 01", "name": "ThisSP"},
              "args": {"required": {"Count": c}, "optional": {}}}, "output": {"return_values": [], "status_codes": s}}
        add([_ss(auth=True), rnd("INVALID_PARAMETER")], "pass", "opal/4.2.9.1", f"Random({cnt})->IP")
        add([_ss(auth=True), rnd("SUCCESS")], "fail", "opal/4.2.9.1", f"Random({cnt})->OK")
    for cnt in [1, 8, 16, 32]:
        rnd_ok = {"input": {"method": {"name": "Random"}, "invoking_id": {"uid": "00 00 00 00 00 00 00 01", "name": "ThisSP"},
                  "args": {"required": {"Count": cnt}, "optional": {}}},
                  "output": {"return_values": [{"result": "0xABCD"}], "status_codes": "SUCCESS"}}
        add([_ss(auth=True), rnd_ok], "pass", "opal/4.2.9.1-ok", f"Random({cnt})->OK")

    return C


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic spec-labeled trajectory splits.")
    parser.add_argument(
        "--include-public-seed",
        action="store_true",
        help="Opt-in only: append public-labelled seed rows from runtime training_data/training_cases.json.",
    )
    args = parser.parse_args()
    if args.include_public_seed:
        # Changed: make public-labelled seed ingestion fail closed.
        # Why: public/eval labels may be used only as holdout/reference, never as supervised training rows.
        parser.error("--include-public-seed is disabled by the LLM-only data contract")

    cases = gen_all()
    random.shuffle(cases)

    # Changed: public-labelled seed rows are excluded unless explicitly requested.
    # Why: public 20 labels must not silently become supervised training anchors.
    public_path = DEFAULT_TRAINING_DATA_DIR / "training_cases.json"
    public_cases = []
    if args.include_public_seed and public_path.exists():
        all_old = json.loads(public_path.read_text())
        for c in all_old:
            if c.get("source", "").startswith("public:"):
                public_cases.append({"steps": c["records"], "label": c["label"],
                                    "spec_rule": "public_ground_truth", "description": c["source"]})

    # ── Split: 60/20/20 random ──
    n = len(cases)
    t1, t2 = int(n * 0.6), int(n * 0.8)
    train_spec = cases[:t1]
    val = cases[t1:t2]
    test = cases[t2:]
    train = train_spec + public_cases

    for name, split in [("Train", train), ("Val", val), ("Test", test)]:
        p = sum(1 for c in split if c["label"] == "pass")
        f = sum(1 for c in split if c["label"] == "fail")
        r = len(set(c["spec_rule"] for c in split))
        print(f"{name}: {len(split):>5} (pass={p}, fail={f}, rules={r})")

    total_p = sum(1 for c in cases if c["label"] == "pass")
    total_f = sum(1 for c in cases if c["label"] == "fail")
    rules = len(set(c["spec_rule"] for c in cases))
    print(f"\nTotal spec: {len(cases)} (pass={total_p}, fail={total_f}, ratio={total_p/len(cases)*100:.1f}%)")
    print(f"+ Public: {len(public_cases)} in train")
    print(f"Rules: {rules}")

    # ── Save ──
    # Changed: spec split 출력 디렉토리를 새 runtime root/env 기반으로 변경.
    # Why: 실행 코드가 이전 /workspace/team6에 산출물을 쓰지 않도록 함.
    out = DEFAULT_TRAINING_DATA_DIR
    out.mkdir(parents=True, exist_ok=True)
    def save(data, path):
        s = [{"records": c["steps"], "label": c["label"], "source": f"spec:{c['spec_rule']}",
              "spec_rule": c["spec_rule"], "description": c["description"]} for c in data]
        path.write_text(json.dumps(s, indent=2, default=str))
        print(f"Saved: {path} ({len(s)})")

    save(train, out / "spec_train.json")
    save(val, out / "spec_val.json")
    save(test, out / "spec_test.json")


if __name__ == "__main__":
    main()
