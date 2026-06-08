<!-- Changed: rewrite the tc11-tc20 archive in Korean with record-by-record pipeline explanations. -->
<!-- Why: the prior archive was case-level only and did not show how each record changes verifier state. -->

# 알고리즘 제출 패키지 Trace 아카이브 - public20 tc11-tc20

작성일: 2026-06-08 KST

## Structural Skeleton

[Original Text/Data] 분석 대상 파일 구조:

```text
data/local/public20/public20_input.jsonl
  - 20 lines.
  - 각 line은 {"sample_id", "input", "source"} dict.
  - input 값은 다시 JSON string이고, 내부에 {"records": [...]}가 있다.

data/local/public20/public20_labels.local.jsonl
  - 20 lines.
  - 각 line은 {"label", "sample_id", "source"} dict.

runs/algorithm/submit/src/solver.py
  - parser helpers
  - ProtocolState
  - StatefulOpalVerifier
  - _run
  - _records
  - _advance_state
  - _final_is_inconsistent
  - _expected_error_for_state
  - _start_session_inconsistent
  - predict / predict_one / Solver.predict

runs/algorithm/submit/src/fsm_shadow.py
  - CandidateAction / Transition / FsmDecision
  - FsmShadow.advance
  - FsmShadow.check_final
  - infer_actions
  - start_session_candidates / get_candidates / set_candidates / activate_candidates
  - DELTA transition table
```

-> [Exact Interpretation] public20 `tc11`부터 `tc20`까지는 모두 label `fail`이고, 입력 단위는 trajectory 전체지만 판정 대상은 마지막 record다.
-> [Detailed Explanation/Example] prefix record들은 `ProtocolState`와 `FsmShadow`를 갱신한다. 마지막 record는 `_final_is_inconsistent()`에서 기존 rulebase 판정을 받고, 그 뒤 `FsmShadow.check_final()`이 expected-status를 보조 확인한다.

## 공통 함수 통과 순서

[Original Text/Data] 단일 실행은 `predict_one(testcase)`에서 시작한다. 제출 evaluator 형태는 `Solver.predict(dataset)`에서 시작한다.

```text
predict_one()
-> StatefulOpalVerifier().verify()
-> _run()

Solver.predict()
-> self.verifier.verify_with_trace(steps)
-> _run()
```

References:
- `runs/algorithm/submit/src/solver.py:1202`
- `runs/algorithm/submit/src/solver.py:1213`

-> [Exact Interpretation] local 단일 검증과 제출 batch 검증은 같은 `StatefulOpalVerifier._run()`으로 들어간다.
-> [Detailed Explanation/Example] `predict_one()`은 label을 모른다. `Solver.predict()`도 label을 보지 않고 input trajectory만 보고 `pass` 또는 `fail`을 만든다.

[Original Text/Data] `_run()`의 핵심 흐름:

```text
records = _records(trajectory)
state = ProtocolState()
fsm_shadow = FsmShadow()

for record in records[:-1]:
    _advance_state(state, record)
    fsm_shadow.advance(record, state)

final_record = records[-1]
inconsistent = _final_is_inconsistent(state, final_record)
base_prediction = "fail" if inconsistent else "pass"
fsm_decision = fsm_shadow.check_final(final_record, state)
prediction = _combine_with_fsm(base_prediction, fsm_decision, state)
```

References:
- `runs/algorithm/submit/src/solver.py:526`
- `runs/algorithm/submit/src/solver.py:651`
- `runs/algorithm/submit/src/solver.py:669`
- `runs/algorithm/submit/src/solver.py:797`
- `runs/algorithm/submit/src/solver.py:548`

-> [Exact Interpretation] 마지막 record는 상태 갱신용이 아니라 검사 대상이다.
-> [Detailed Explanation/Example] 예를 들어 prefix에서 `Set C_PIN SUCCESS`가 있으면 `_advance_state()`가 `known_secrets`를 갱신한다. 이후 final `StartSession`의 `HostChallenge`가 그 secret과 맞는지 `_start_session_inconsistent()`가 검사한다.

[Original Text/Data] final method가 `Get`, `Set`, `Activate`, `GenKey`, `Read`, `Write`, `EndSession` 계열이면 `_final_is_inconsistent()`는 먼저 `_expected_error_for_state()`를 확인하고, expected error가 없는데 status가 error이면 known-field success 여부를 검사한다.

References:
- `runs/algorithm/submit/src/solver.py:855`
- `runs/algorithm/submit/src/solver.py:1009`

-> [Exact Interpretation] final response가 error라고 무조건 `fail`이 아니다. 현재 state에서 그 error가 기대되는 error인지 먼저 본다.
-> [Detailed Explanation/Example] session 없이 `Set`이면 `NOT_AUTHORIZED`가 기대될 수 있다. 반대로 known C_PIN field read처럼 성공해야 하는 명령이 `NOT_AUTHORIZED`를 반환하면 `KNOWN_FIELD_EXPECTED_SUCCESS`로 `fail`이다.

[Original Text/Data] FSM shadow는 final record를 abstract action 후보로 바꾼 뒤 `DELTA[(state, action)]`의 expected status와 실제 status를 비교한다.

References:
- `runs/algorithm/submit/src/fsm_shadow.py:47`
- `runs/algorithm/submit/src/fsm_shadow.py:78`
- `runs/algorithm/submit/src/fsm_shadow.py:255`

-> [Exact Interpretation] 새 알고리즘은 기존 rulebase를 대체하지 않고, FSM expected-status evidence를 하나 더 붙인다.
-> [Detailed Explanation/Example] 기존 base가 `fail`이고 FSM이 `unknown`이면 그대로 `fail`이다. FSM이 high-confidence일 때만 제한적으로 rescue/veto가 가능하다.

## tc11

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:11`, `data/local/public20/public20_labels.local.jsonl:11`
- record 수: 1
- 진입점: `predict_one()` 또는 `Solver.predict()`
- 기존 rulebase 핵심: `_records()` -> `_final_is_inconsistent()` -> `PROPERTIES_TARGET` -> `PROPERTIES_PAYLOAD`
- 새 코드 추가분: `FsmShadow.check_final()` -> `_combine_with_fsm()`

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc11", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] tc11의 마지막 response는 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] trajectory가 record 1개뿐이라 이 record가 곧 final record다.

[Original Text/Data] record 1:

```text
01 Properties INVALID_PARAMETER
   invoking=Session Manager UID, uid=00 00 00 00 00 00 00 FF
   return_values=[]
```

-> [Exact Interpretation] `Properties`는 Session Manager UID에 대해 호출되었으므로 target 자체는 정상이다. 그러나 status가 `INVALID_PARAMETER`이고 payload가 비어 있다.
-> [Detailed Explanation/Example] `_final_is_inconsistent()`는 먼저 `PROPERTIES_TARGET`에서 `inconsistent=False`를 기록한다. 그 다음 `PROPERTIES_PAYLOAD`에서 `status != success` 또는 properties payload 없음 조건으로 `inconsistent=True`를 반환한다. base prediction은 `fail`.

[Original Text/Data] FSM shadow trace:

```text
base=fail, fsm=inconsistent, confidence=1.000,
expected=['success'], actions=['PROPERTIES'], final=fail
```

-> [Exact Interpretation] FSM도 `PROPERTIES`의 expected status를 `SUCCESS`로 본다.
-> [Detailed Explanation/Example] 실제 status가 `INVALID_PARAMETER`라서 FSM도 inconsistent다. 새 FSM 단계는 기존 `fail`을 바꾸지 않는다.

## tc12

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:12`, `data/local/public20/public20_labels.local.jsonl:12`
- record 수: 2
- 진입점: `predict_one()` 또는 `Solver.predict()`
- 기존 rulebase 핵심: `_advance_state()` -> `_final_is_inconsistent()` -> `KNOWN_FIELD_EXPECTED_SUCCESS`
- 새 코드 추가분: `FsmShadow.advance()` -> `FsmShadow.check_final()`

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc12", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final `Get` response가 틀린 것으로 판정되어야 한다.
-> [Detailed Explanation/Example] record 1은 prefix state 구성용이고, record 2가 final 검사 대상이다.

[Original Text/Data] record 1:

```text
01 StartSession SUCCESS
   SPID=0000020500000001, Write=1
   HostChallenge 없음
   return HostSessionID=00000001, SPSessionID=000065ab
```

-> [Exact Interpretation] 성공한 세션 시작 record다. HostChallenge가 없으므로 인증은 되지 않았지만 active session은 생긴다.
-> [Detailed Explanation/Example] `_advance_state()`는 `active_sessions`에 `00000001`을 넣고, `authenticated=False`, `session_write=True`를 기록한다. FSM shadow는 `START_RW_ADMIN_NOBODY` 계열 성공 prefix로 상태를 전진시킨다.

[Original Text/Data] record 2:

```text
02 Get NOT_AUTHORIZED
   invoking=C_PIN, uid=00 00 00 0B 00 00 84 02
   Cellblock=startColumn 3, endColumn 3
   return_values=[]
```

-> [Exact Interpretation] final은 C_PIN/MSID의 column 3 read다. 이 rulebase는 이 field read를 known-field success case로 본다.
-> [Detailed Explanation/Example] `_final_is_inconsistent()`에서 expected state error는 없다. 그런데 status가 `NOT_AUTHORIZED`라서 `_known_field_access_expected_success()`를 확인하고 `expected_success=cpin:3`을 얻는다. `KNOWN_FIELD_EXPECTED_SUCCESS`가 `actual=notauthorized`를 기록하고 `fail`을 반환한다.

[Original Text/Data] FSM shadow trace:

```text
base=fail, fsm=inconsistent, confidence=0.950,
expected=['success'], actions=['GET_MSID_PIN'], final=fail
```

-> [Exact Interpretation] FSM도 final `Get C_PIN 84 02 column 3`을 `GET_MSID_PIN`으로 보고 `SUCCESS`를 기대한다.
-> [Detailed Explanation/Example] 실제 status가 `NOT_AUTHORIZED`라서 FSM도 inconsistent다. 최종 prediction은 `fail`.

## tc13

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:13`, `data/local/public20/public20_labels.local.jsonl:13`
- record 수: 7
- 진입점: `predict_one()` 또는 `Solver.predict()`
- 기존 rulebase 핵심: `_advance_state()`의 `SET_CPIN_SECRET` -> `_start_session_inconsistent()`
- 새 코드 추가분: `FsmShadow.advance()` -> `start_session_candidates()` -> `FsmShadow.check_final()`

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc13", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final `StartSession NOT_AUTHORIZED`가 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] prefix에서 C_PIN을 새 값으로 설정했고, final은 그 값을 그대로 HostChallenge로 사용한다.

[Original Text/Data] record 1:

```text
01 StartSession SUCCESS
   SPID=0000020500000001, Write=1
   HostChallenge 없음
   return HostSessionID=00000001, SPSessionID=00006935
```

-> [Exact Interpretation] Admin SP RW 세션이 열리지만 인증 challenge는 없다.
-> [Detailed Explanation/Example] `_advance_state()`는 `active_sessions`를 만들고 `authenticated=False`, `session_write=True`로 둔다.

[Original Text/Data] record 2:

```text
02 Get SUCCESS
   invoking=C_PIN, uid=00 00 00 0B 00 00 84 02
   Cellblock=3..3
   return column 3 = MJDL5TDSXBZ7NW3TE2PCESSNTLGYSBOW
```

-> [Exact Interpretation] MSID/C_PIN 값을 읽는 성공 record다.
-> [Detailed Explanation/Example] 기존 `_advance_state()`는 `Get` 성공을 별도 state로 쓰지 않는다. FSM shadow는 `GET_MSID_PIN` 성공 전이로 가능한 FSM 상태를 좁힌다.

[Original Text/Data] record 3:

```text
03 EndSession SUCCESS
```

-> [Exact Interpretation] 열린 세션을 닫는다.
-> [Detailed Explanation/Example] `_advance_state()`는 `active_sessions.clear()`를 수행하고 `authenticated=False`가 되게 만든다.

[Original Text/Data] record 4:

```text
04 StartSession SUCCESS
   HostChallenge=3P5ADJBHFA4JJN57CZYR3FW1AEMDKF8J
   HostSigningAuthority=0000000900000006
   SPID=0000020500000001, Write=1
```

-> [Exact Interpretation] HostChallenge가 있으므로 rulebase는 인증 시도가 있었다고 본다.
-> [Detailed Explanation/Example] `_advance_state()`는 `authenticated=True`, `session_write=True`로 갱신한다. 이 상태에서 다음 `Set C_PIN`이 성공했으므로 secret update로 인정된다.

[Original Text/Data] record 5:

```text
05 Set SUCCESS
   invoking=C_PIN, uid=00 00 00 0B 00 00 00 01
   Values[3]=a5a1c7fc3824f652a9114cc69649d0b715f7d4c6c5e1f8bbfc907b425ba87284
```

-> [Exact Interpretation] C_PIN column 3이 새 secret 값으로 설정된다.
-> [Detailed Explanation/Example] `_advance_state()`는 `SET_CPIN_SECRET`로 `known_secrets`에 해당 값을 넣고, `SET_OBJECT_FIELDS`로 object field column 3도 저장한다.

[Original Text/Data] record 6:

```text
06 EndSession SUCCESS
```

-> [Exact Interpretation] 세션을 닫는다.
-> [Detailed Explanation/Example] active session은 사라지지만 `known_secrets`는 유지된다. final StartSession이 이 secret을 사용할 수 있는지 판단하는 데 사용된다.

[Original Text/Data] record 7:

```text
07 StartSession NOT_AUTHORIZED
   HostChallenge=a5a1c7fc3824f652a9114cc69649d0b715f7d4c6c5e1f8bbfc907b425ba87284
   HostSigningAuthority=0000000900000006
```

-> [Exact Interpretation] final HostChallenge가 record 5에서 설정한 known secret과 같다. 따라서 expected status는 `SUCCESS`다.
-> [Detailed Explanation/Example] `_start_session_inconsistent()`에서 `challenge in state.known_secrets and status != success` 조건이 참이므로 `inconsistent=True`. FSM shadow도 final을 `START_RW_ADMIN_SID`로 추론하고 expected `SUCCESS`와 actual `NOT_AUTHORIZED` 불일치를 기록한다. 최종 prediction은 `fail`.

## tc14

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:14`, `data/local/public20/public20_labels.local.jsonl:14`
- record 수: 10
- 기존 rulebase 핵심: `_advance_state()`의 `SET_CPIN_SECRET` 누적 -> `_start_session_inconsistent()`
- 새 코드 추가분: `start_session_candidates()`가 `START_RW_ADMIN_SID_WRONG_PW`를 만든다.

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc14", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final `StartSession SUCCESS`가 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] final은 wrong HostChallenge로 성공한 것처럼 보인다.

[Original Text/Data] records:

```text
01 StartSession SUCCESS, no HostChallenge, SPID=0000020500000001, Write=1
02 Get SUCCESS, C_PIN 84 02 column 3 -> MJDL5T...
03 EndSession SUCCESS
04 StartSession SUCCESS, HostChallenge=3P5ADJ..., HSA=0000000900000006
05 Set SUCCESS, C_PIN Values[3]=3e06061d...
06 EndSession SUCCESS
07 StartSession SUCCESS, HostChallenge=3e06061d...
08 Set SUCCESS, C_PIN Values[3]=f620e538...
09 EndSession SUCCESS
10 StartSession SUCCESS, HostChallenge=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

-> [Exact Interpretation] record 5와 record 8이 known C_PIN secret을 만든다. record 10의 HostChallenge는 그 집합에 없다.
-> [Detailed Explanation/Example] record 1은 unauthenticated session, record 4와 7은 authenticated session으로 state를 만든다. record 5와 8은 `_advance_state()`에서 `SET_CPIN_SECRET`을 발생시킨다. record 9는 session만 닫고 secret은 유지한다.

[Original Text/Data] final 판정 조건:

```python
if challenge and state.known_secrets:
    if challenge not in state.known_secrets:
        return status != "notauthorized"
```

Reference:
- `runs/algorithm/submit/src/solver.py:1081`

-> [Exact Interpretation] known secret과 다른 challenge면 expected status는 `NOT_AUTHORIZED`다.
-> [Detailed Explanation/Example] final status는 `SUCCESS`이므로 `status != "notauthorized"`가 참이다. 기존 rulebase base prediction은 `fail`.

[Original Text/Data] FSM shadow final trace:

```text
base=fail, fsm=inconsistent, confidence=0.950,
expected=['notauthorized'], actions=['START_RW_ADMIN_SID_WRONG_PW'], final=fail
```

-> [Exact Interpretation] FSM도 final을 wrong password StartSession으로 본다.
-> [Detailed Explanation/Example] `start_session_candidates()`는 `challenge and known and challenge not in known` 조건으로 `START_RW_ADMIN_SID_WRONG_PW`를 만든다. DELTA expected status는 `NOT_AUTHORIZED`인데 actual은 `SUCCESS`라 inconsistent다.

## tc15

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:15`, `data/local/public20/public20_labels.local.jsonl:15`
- record 수: 9
- 기존 rulebase 핵심: `_expected_error_for_state()` -> `_activate_target_invalid()`
- 새 코드 추가분: FSM shadow는 low-confidence `unknown`이라 base 판정 유지

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc15", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final `Activate SUCCESS`가 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] final Activate target UID가 rulebase의 valid Locking SP target shape와 맞지 않는다.

[Original Text/Data] records:

```text
01 StartSession SUCCESS, Admin SP, no HostChallenge
02 Get SUCCESS, C_PIN 84 02 column 3 -> MSID-like value
03 EndSession SUCCESS
04 StartSession SUCCESS, Admin SP, HostChallenge=3P5ADJ..., HSA=SID
05 Set SUCCESS, C_PIN Values[3]=3e06061d...
06 EndSession SUCCESS
07 StartSession SUCCESS, Admin SP, HostChallenge=3e06061d...
08 Get SUCCESS, SP uid=00 00 02 05 00 00 00 02, column 6 -> 8
09 Activate SUCCESS, SP uid=00 00 01 05 00 00 00 04
```

-> [Exact Interpretation] record 1-8은 세션과 C_PIN state를 만든다. final record 9는 Activate target이 핵심이다.
-> [Detailed Explanation/Example] record 5의 `Set C_PIN`은 `known_secrets`를 만든다. record 7은 그 secret으로 authenticated 상태가 된다. record 8은 SP 정보를 읽지만 final 판정은 record 9의 invoking UID에 의해 결정된다.

[Original Text/Data] `_activate_target_invalid()`:

```text
if "sp" not in invoking: return True
return bool(invoking_uid) and not invoking_uid.startswith("00000205")
```

Reference:
- `runs/algorithm/submit/src/solver.py:1053`

-> [Exact Interpretation] Activate는 SP target이어야 하고 UID는 `00000205...` shape여야 한다.
-> [Detailed Explanation/Example] final uid는 compact하면 `0000010500000004`라 `00000205`로 시작하지 않는다. `_expected_error_for_state()`는 expected `invalidparameter`를 반환한다. actual은 `success`라 `PRECONDITION_EXPECTED_ERROR expected=invalidparameter, actual=success`, 최종 `fail`.

[Original Text/Data] FSM shadow trace:

```text
base=fail, fsm=unknown, confidence=0.572,
expected=['fail'], actions=['ACTIVATE_ISSUED_SP'], final=fail
```

-> [Exact Interpretation] FSM은 이 case에서 충분히 높은 confidence가 아니므로 결과를 바꾸지 않는다.
-> [Detailed Explanation/Example] final output `fail`은 기존 rulebase의 invalid Activate target check에서 나온다.

## tc16

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:16`, `data/local/public20/public20_labels.local.jsonl:16`
- record 수: 21
- 기존 rulebase 핵심: `_final_is_inconsistent()` -> `KNOWN_FIELD_EXPECTED_SUCCESS`
- 새 코드 추가분: FSM shadow는 possible success action을 보지만 confidence가 낮아 override 없음

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc16", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final `Set Authority INVALID_PARAMETER`가 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] rulebase는 Authority column 5 update를 known-field success operation으로 본다.

[Original Text/Data] records 1-10:

```text
01 StartSession SUCCESS, Admin SP, no HostChallenge
02 Get SUCCESS, C_PIN 84 02 column 3
03 EndSession SUCCESS
04 StartSession SUCCESS, Admin SP, HostChallenge=3P5ADJ...
05 Set SUCCESS, C_PIN Values[3]=3e06061d...
06 EndSession SUCCESS
07 StartSession SUCCESS, Admin SP, HostChallenge=3e06061d...
08 Get SUCCESS, SP uid=00 00 02 05 00 00 00 02, column 6 -> 8
09 Activate SUCCESS, SP uid=00 00 02 05 00 00 00 02
10 EndSession SUCCESS
```

-> [Exact Interpretation] 이 prefix는 Admin SP에서 credential을 설정하고 Locking SP를 activate한다.
-> [Detailed Explanation/Example] record 5는 `known_secrets`를 갱신한다. record 9는 `_advance_state()`에서 `ACTIVATE_SP_EFFECT`를 발생시켜 activated SP context를 만든다.

[Original Text/Data] records 11-20:

```text
11 StartSession SUCCESS, Locking SP, no HostChallenge
12 Get SUCCESS, LockingInfo column 4 -> 00000008
13 EndSession SUCCESS
14 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
15 Get SUCCESS, MBRControl columns 1..2 -> 0,0
16 EndSession SUCCESS
17 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
18 Get SUCCESS, Locking columns 3..8 -> 0/0/0/0/0/0
19 EndSession SUCCESS
20 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
```

-> [Exact Interpretation] Locking SP 안에서 필요한 조회들이 정상적으로 성공했고, final `Set Authority`를 실행할 active/authenticated session이 준비된다.
-> [Detailed Explanation/Example] 기존 rulebase는 `Get` 성공 자체를 모두 state로 저장하지는 않지만, active/authenticated/session state는 유지한다. FSM shadow는 여러 Locking path 후보를 따라간다.

[Original Text/Data] record 21:

```text
21 Set INVALID_PARAMETER
   invoking=Authority, uid=00 00 00 09 00 03 00 01
   Values=[{"5": 1}]
   return_values=[]
```

-> [Exact Interpretation] final은 Authority table column 5를 enable하려는 Set이다. 이 operation은 expected success로 분류된다.
-> [Detailed Explanation/Example] `_expected_error_for_state()`는 expected error를 내지 않는다. status가 success가 아니므로 `_known_field_access_expected_success()`가 `authority:5`를 반환한다. `KNOWN_FIELD_EXPECTED_SUCCESS expected_success=authority:5, actual=invalidparameter`라 `fail`.

[Original Text/Data] FSM shadow trace:

```text
base=fail, fsm=unknown, confidence=0.242,
expected=['success'], actions=['SET_AUTHORITY_ENABLED', 'SET_USER_ENABLED'], final=fail
```

-> [Exact Interpretation] FSM도 성공 action 후보를 보지만 confidence가 낮다.
-> [Detailed Explanation/Example] `_combine_with_fsm()`은 `unknown` 또는 confidence `< 0.70`이면 base prediction을 그대로 둔다. 최종 `fail`.

## tc17

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:17`, `data/local/public20/public20_labels.local.jsonl:17`
- record 수: 26
- 기존 rulebase 핵심: `_advance_state()`의 `SET_CPIN_SECRET` -> `_start_session_inconsistent()`
- 새 코드 추가분: FSM shadow는 possible Locking StartSession success path를 보지만 low-confidence unknown

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc17", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final `StartSession NOT_AUTHORIZED`가 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] record 24에서 final HostChallenge와 같은 C_PIN secret을 설정했기 때문이다.

[Original Text/Data] records 1-10:

```text
01 StartSession SUCCESS, Admin SP, no HostChallenge
02 Get SUCCESS, C_PIN 84 02 column 3
03 EndSession SUCCESS
04 StartSession SUCCESS, Admin SP, HostChallenge=3P5ADJ...
05 Set SUCCESS, C_PIN SID Values[3]=3e06061d...
06 EndSession SUCCESS
07 StartSession SUCCESS, Admin SP, HostChallenge=3e06061d...
08 Get SUCCESS, SP uid=00 00 02 05 00 00 00 02, column 6 -> 8
09 Activate SUCCESS, SP uid=00 00 02 05 00 00 00 02
10 EndSession SUCCESS
```

-> [Exact Interpretation] Admin credential과 Locking SP activation이 완료된다.
-> [Detailed Explanation/Example] record 5는 `known_secrets`에 SID secret을 넣고, record 9는 `activated_sps`를 갱신한다.

[Original Text/Data] records 11-19:

```text
11 StartSession SUCCESS, Locking SP, no HostChallenge
12 Get SUCCESS, LockingInfo column 4 -> 00000008
13 EndSession SUCCESS
14 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
15 Get SUCCESS, MBRControl columns 1..2 -> 0,0
16 EndSession SUCCESS
17 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
18 Get SUCCESS, Locking columns 3..8 -> all zeros / unlocked fields
19 EndSession SUCCESS
```

-> [Exact Interpretation] Locking SP 조회 path가 정상적으로 지나간다.
-> [Detailed Explanation/Example] session은 열리고 닫히지만, prefix success들이 final 판단의 맥락을 만든다. 특히 이후 Authority/User enable과 C_PIN 설정이 가능해진다.

[Original Text/Data] records 20-25:

```text
20 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
21 Set SUCCESS, Authority uid=00 00 00 09 00 03 00 01, Values[5]=1
22 EndSession SUCCESS
23 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
24 Set SUCCESS, C_PIN uid=00 00 00 0B 00 03 00 01,
   Values[3]=9dd74dd6adfe9be82a1f1204ec8444cda547c2a6cffab3f54871aea6e36ea59f
25 EndSession SUCCESS
```

-> [Exact Interpretation] record 21은 user/authority를 enable하고, record 24는 final HostChallenge에 쓰일 C_PIN secret을 설정한다.
-> [Detailed Explanation/Example] `_advance_state()`는 record 24에서 `SET_CPIN_SECRET`을 기록한다. 이 값은 `known_secrets`에 남아 final record 26을 검사하는 데 사용된다.

[Original Text/Data] record 26:

```text
26 StartSession NOT_AUTHORIZED
   SPID=0000020500000002
   HostSigningAuthority=0000000900030001
   HostChallenge=9dd74dd6adfe9be82a1f1204ec8444cda547c2a6cffab3f54871aea6e36ea59f
```

-> [Exact Interpretation] final HostChallenge는 record 24에서 설정한 known secret과 같다. 따라서 `SUCCESS`가 기대된다.
-> [Detailed Explanation/Example] `_start_session_inconsistent()`는 `challenge in state.known_secrets and status != success`로 `inconsistent=True`를 반환한다. FSM shadow는 `START_RW_LOCKING_ADMIN1` success path를 후보로 보지만 confidence가 낮아 base `fail`을 유지한다.

## tc18

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:18`, `data/local/public20/public20_labels.local.jsonl:18`
- record 수: 21
- 기존 rulebase 핵심: `_final_is_inconsistent()` -> `KNOWN_FIELD_EXPECTED_SUCCESS`
- 새 코드 추가분: FSM shadow는 `GET_LOCKING_RANGE` success 후보를 보지만 low-confidence unknown

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc18", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final `Get Locking INVALID_PARAMETER`가 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] 같은 Locking object의 columns 3..8은 prefix record 18에서 이미 정상적으로 읽힌 shape다.

[Original Text/Data] records 1-10:

```text
01 StartSession SUCCESS, Admin SP
02 Get SUCCESS, C_PIN 84 02 column 3
03 EndSession SUCCESS
04 StartSession SUCCESS, Admin SP, HostChallenge=3P5ADJ...
05 Set SUCCESS, C_PIN Values[3]=3e06061d...
06 EndSession SUCCESS
07 StartSession SUCCESS, Admin SP, HostChallenge=3e06061d...
08 Get SUCCESS, SP uid=00 00 02 05 00 00 00 02, column 6 -> 8
09 Activate SUCCESS, SP uid=00 00 02 05 00 00 00 02
10 EndSession SUCCESS
```

-> [Exact Interpretation] Admin setup과 Locking SP activation이 완료된다.
-> [Detailed Explanation/Example] record 9는 `ACTIVATE_SP_EFFECT`를 남기며 이후 Locking SP 접근 path를 만든다.

[Original Text/Data] records 11-20:

```text
11 StartSession SUCCESS, Locking SP, no HostChallenge
12 Get SUCCESS, LockingInfo column 4 -> 00000008
13 EndSession SUCCESS
14 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
15 Get SUCCESS, MBRControl columns 1..2 -> 0,0
16 EndSession SUCCESS
17 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
18 Get SUCCESS, Locking columns 3..8 -> values returned
19 EndSession SUCCESS
20 StartSession SUCCESS, Locking SP, HostChallenge=3e06061d..., HSA=Admin1
```

-> [Exact Interpretation] final 직전에는 Locking SP authenticated session이 다시 열려 있다.
-> [Detailed Explanation/Example] record 18에서 같은 Locking columns 3..8이 성공한 적이 있다. final record 21의 동일한 known-field read가 error를 반환하면 fail 근거가 된다.

[Original Text/Data] record 21:

```text
21 Get INVALID_PARAMETER
   invoking=Locking, uid=00 00 08 02 00 00 00 01
   Cellblock=startColumn 3, endColumn 8
   return_values=[]
```

-> [Exact Interpretation] known Locking table columns 3..8 read는 success가 기대된다.
-> [Detailed Explanation/Example] `_known_field_access_expected_success()`가 `locking:3,4,5,6,7,8`을 반환한다. actual은 `invalidparameter`라 `KNOWN_FIELD_EXPECTED_SUCCESS`로 `fail`.

## tc19

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:19`, `data/local/public20/public20_labels.local.jsonl:19`
- record 수: 27
- 기존 rulebase 핵심: `_advance_state()`의 `SET_OBJECT_FIELDS` -> `KNOWN_FIELD_EXPECTED_SUCCESS`
- 새 코드 추가분: FSM shadow는 final에서 expected status를 만들지 못해 unknown

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc19", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final `Get MBRControl FAIL`이 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] prefix에서 MBRControl columns 1,2를 성공적으로 읽고 설정했으므로 final read도 성공해야 한다.

[Original Text/Data] records 1-19:

```text
01 StartSession SUCCESS, Admin SP
02 Get SUCCESS, C_PIN 84 02 column 3
03 EndSession SUCCESS
04 StartSession SUCCESS, Admin SP, HostChallenge=3P5ADJ...
05 Set SUCCESS, C_PIN Values[3]=3e06061d...
06 EndSession SUCCESS
07 StartSession SUCCESS, Admin SP, HostChallenge=3e06061d...
08 Get SUCCESS, SP column 6 -> 8
09 Activate SUCCESS, Locking SP
10 EndSession SUCCESS
11 StartSession SUCCESS, Locking SP
12 Get SUCCESS, LockingInfo column 4 -> 00000008
13 EndSession SUCCESS
14 StartSession SUCCESS, Locking SP, HSA=Admin1
15 Get SUCCESS, MBRControl columns 1..2 -> 0,0
16 EndSession SUCCESS
17 StartSession SUCCESS, Locking SP, HSA=Admin1
18 Get SUCCESS, Locking columns 3..8
19 EndSession SUCCESS
```

-> [Exact Interpretation] 기본 Locking SP setup과 MBRControl read path가 정상적으로 구성된다.
-> [Detailed Explanation/Example] record 15는 MBRControl columns 1,2가 실제로 읽힐 수 있음을 보여준다. 이후 record 21,24에서 같은 object의 field state가 갱신된다.

[Original Text/Data] records 20-26:

```text
20 StartSession SUCCESS, Locking SP, HSA=Admin1
21 Set SUCCESS, MBRControl Values[2]=1
22 EndSession SUCCESS
23 StartSession SUCCESS, Locking SP, HSA=Admin1
24 Set SUCCESS, MBRControl Values[1]=1
25 EndSession SUCCESS
26 StartSession SUCCESS, Locking SP, HSA=Admin1
```

-> [Exact Interpretation] MBRControl columns 1과 2에 대한 successful Set이 prefix에 있다.
-> [Detailed Explanation/Example] `_advance_state()`는 record 21과 24에서 `SET_OBJECT_FIELDS`를 발생시켜 MBRControl object field 값을 저장한다.

[Original Text/Data] record 27:

```text
27 Get FAIL
   invoking=MBRControl, uid=00 00 08 03 00 00 00 01
   Cellblock=startColumn 1, endColumn 2
   return_values=[]
```

-> [Exact Interpretation] MBRControl columns 1,2 read는 success가 기대된다.
-> [Detailed Explanation/Example] `_known_field_access_expected_success()`가 `mbrcontrol:1,2`를 반환한다. actual은 `fail`이라 `KNOWN_FIELD_EXPECTED_SUCCESS`에서 final `fail`. FSM shadow는 final action을 확정하지 못해 `unknown`, override 없음.

## tc20

### Structural Skeleton

- 데이터: `data/local/public20/public20_input.jsonl:20`, `data/local/public20/public20_labels.local.jsonl:20`
- record 수: 39
- 기존 rulebase 핵심: `_advance_state()`의 `WRITE_PAYLOAD_EFFECT`와 `GENKEY_EFFECT` -> `_read_payload_inconsistent()`
- 새 코드 추가분: FSM shadow는 final data-command path에서 unknown, base `fail` 유지

[Original Text/Data] label line:

```json
{"label": "fail", "sample_id": "tc20", "source": "public20_shape.local_reference"}
```

-> [Exact Interpretation] final data `Read` response가 틀린 response로 판정되어야 한다.
-> [Detailed Explanation/Example] `Write` 후 `GenKey`가 성공했는데 final `Read`가 기존 pattern을 그대로 반환한다.

[Original Text/Data] records 1-22:

```text
01 StartSession SUCCESS, Admin SP
02 Get SUCCESS, C_PIN 84 02 column 3
03 EndSession SUCCESS
04 StartSession SUCCESS, Admin SP, HostChallenge=3P5ADJ...
05 Set SUCCESS, C_PIN Values[3]=3e06061d...
06 EndSession SUCCESS
07 StartSession SUCCESS, Admin SP, HostChallenge=3e06061d...
08 Get SUCCESS, SP column 6 -> 8
09 Activate SUCCESS, Locking SP
10 EndSession SUCCESS
11 StartSession SUCCESS, Locking SP
12 Get SUCCESS, LockingInfo column 4 -> 00000008
13 EndSession SUCCESS
14 StartSession SUCCESS, Locking SP, HSA=Admin1
15 Get SUCCESS, MBRControl columns 1..2 -> 0,0
16 EndSession SUCCESS
17 StartSession SUCCESS, Locking SP, HSA=Admin1
18 Get SUCCESS, Locking columns 3..8
19 EndSession SUCCESS
20 StartSession SUCCESS, Locking SP, HSA=Admin1
21 Set SUCCESS, Locking Values[3,4,5,6,7,8]=0/00020000/0/0/0/0
22 EndSession SUCCESS
```

-> [Exact Interpretation] Locking SP와 Locking range 설정 prefix다.
-> [Detailed Explanation/Example] record 21은 `_advance_state()`에서 `SET_OBJECT_FIELDS columns=3,4,5,6,7,8`을 저장한다. 아직 final fail의 직접 원인은 아니지만 later read/write legality context를 만든다.

[Original Text/Data] records 23-32:

```text
23 StartSession SUCCESS, Locking SP, HSA=Admin1
24 Get SUCCESS, Locking column 10 -> 0000080600030001
25 GenKey SUCCESS, K_AES_256
26 EndSession SUCCESS
27 StartSession SUCCESS, Locking SP, HSA=Admin1
28 Set SUCCESS, Locking Values[5]=1, Values[6]=1
29 EndSession SUCCESS
30 StartSession SUCCESS, Locking SP, HSA=Admin1
31 Set SUCCESS, Locking Values[7]=0, Values[8]=0
32 EndSession SUCCESS
```

-> [Exact Interpretation] key object 조회와 GenKey, 그리고 Locking field 추가 설정이 일어난다.
-> [Detailed Explanation/Example] record 25의 `GenKey`는 아직 이전 write payload가 없으므로 trace는 `GENKEY_EFFECT after_write=False`다. 이후 write가 발생해야 stale-read 판단 조건이 생긴다.

[Original Text/Data] records 33-38:

```text
33 Write SUCCESS(command-result)
   LBA=80 ~ 87, pattern=8E, result=pass
34 Read SUCCESS(command-result)
   LBA=80 ~ 87, result=Pattern 8E
35 StartSession SUCCESS, Locking SP, HSA=Admin1
36 Get SUCCESS, Locking column 10 -> 0000080600030001
37 GenKey SUCCESS, K_AES_256
38 EndSession SUCCESS
```

-> [Exact Interpretation] record 33이 media payload `8E`를 쓰고, record 37이 write 이후 key regeneration을 수행한다.
-> [Detailed Explanation/Example] `_advance_state()`는 record 33에서 `written_payloads["80 ~ 87"]="8E"`를 저장하고 `generated_key_after_write=False`로 둔다. record 37에서 `state.written_payloads`가 존재하므로 `generated_key_after_write=True`가 된다.

[Original Text/Data] record 39:

```text
39 Read SUCCESS(command-result)
   LBA=80 ~ 87
   result=8E
```

-> [Exact Interpretation] final Read가 record 33에서 쓴 old pattern `8E`를 그대로 반환한다.
-> [Detailed Explanation/Example] `_read_payload_inconsistent()`는 `generated_key_after_write=True`이고 final payload가 stored write payload와 equivalent하면 stale payload로 본다. trace는 `READ_PAYLOAD inconsistent=True`; base prediction은 `fail`. FSM shadow는 data-command path를 충분히 추적하지 못해 `unknown`, override 없음.

## 최종 요약

[Original Text/Data] tc11-tc20 판정 요약:

```text
tc11: Properties가 SUCCESS+payload 대신 INVALID_PARAMETER+empty payload를 반환.
tc12: C_PIN/MSID Get이 SUCCESS 대신 NOT_AUTHORIZED를 반환.
tc13: known C_PIN HostChallenge StartSession이 SUCCESS 대신 NOT_AUTHORIZED를 반환.
tc14: unknown/wrong HostChallenge StartSession이 NOT_AUTHORIZED 대신 SUCCESS를 반환.
tc15: invalid Activate SP target이 INVALID_PARAMETER 대신 SUCCESS를 반환.
tc16: Authority field Set이 SUCCESS 대신 INVALID_PARAMETER를 반환.
tc17: known Locking SP credential StartSession이 SUCCESS 대신 NOT_AUTHORIZED를 반환.
tc18: Locking table Get이 SUCCESS 대신 INVALID_PARAMETER를 반환.
tc19: MBRControl Get이 SUCCESS 대신 FAIL을 반환.
tc20: GenKey 이후 Read가 old written payload를 그대로 반환.
```

-> [Exact Interpretation] fail 10개는 대부분 prefix가 실패해서 fail이 아니라, prefix가 만든 state와 final response가 충돌해서 fail이다.
-> [Detailed Explanation/Example] 현재 알고리즘의 핵심은 `records[:-1]`로 `ProtocolState`를 만들고 `records[-1]`이 그 state에서 허용되는 response인지 보는 것이다. FSM shadow는 이 결론을 expected-status 관점에서 보조 확인하되, low-confidence이면 개입하지 않는다.

## Record별 상세 부록

[Original Text/Data] 아래 표는 각 record가 verifier 내부에서 어떤 역할을 하는지 record 단위로 다시 펼친 것이다.

-> [Exact Interpretation] `prefix` record는 `_advance_state()`와 `FsmShadow.advance()`를 통과한다. `final` record는 `_final_is_inconsistent()`와 `FsmShadow.check_final()`을 통과한다.
-> [Detailed Explanation/Example] `StartSession SUCCESS` prefix는 세션/auth/write 상태를 만들고, `Set SUCCESS` prefix는 C_PIN secret이나 object field를 저장한다. final record는 그 누적 state와 자기 output status/payload가 맞는지 검사된다.

### tc11 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | final `Properties INVALID_PARAMETER`, Session Manager UID, `return_values=[]` | `_final_is_inconsistent()`가 `PROPERTIES_TARGET`은 정상으로 보지만 `PROPERTIES_PAYLOAD`에서 `SUCCESS + properties payload`가 없다고 판단한다. FSM은 `PROPERTIES -> SUCCESS`를 기대하므로 둘 다 `fail`. |

### tc12 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP, `Write=1`, HostChallenge 없음 | `_advance_state()`가 `active_sessions={00000001}`, `authenticated=False`, `session_write=True`를 만든다. FSM은 unauthenticated Admin RW session 쪽으로 전진한다. |
| 2 | final `Get C_PIN NOT_AUTHORIZED`, uid `00 00 00 0B 00 00 84 02`, Cellblock `3..3` | expected state error는 없다. `_known_field_access_expected_success()`가 `cpin:3`을 반환하므로 `NOT_AUTHORIZED`는 unexpected error다. FSM도 `GET_MSID_PIN -> SUCCESS`를 기대한다. 최종 `fail`. |

### tc13 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP, HostChallenge 없음 | active session을 만들고 `authenticated=False`, `session_write=True`가 된다. |
| 2 | prefix `Get C_PIN SUCCESS`, uid `84 02`, Cellblock `3..3`, MSID-like value 반환 | 기존 `ProtocolState`는 `Get` 성공을 저장하지 않는다. FSM shadow는 `GET_MSID_PIN` 성공 path로 상태 후보를 좁힌다. |
| 3 | prefix `EndSession SUCCESS` | `_advance_state()`가 active session을 clear하고 auth를 false 쪽으로 정리한다. |
| 4 | prefix `StartSession SUCCESS`, HostChallenge `3P5ADJ...`, HSA `0000000900000006` | HostChallenge가 있으므로 `_advance_state()`는 인증 시도로 보고 `authenticated=True`를 만든다. |
| 5 | prefix `Set C_PIN SUCCESS`, Values[3]=`a5a1c7fc...` | `_advance_state()`가 `known_secrets`에 `a5a1c7fc...`를 넣고, `object_fields`에도 C_PIN column 3을 저장한다. |
| 6 | prefix `EndSession SUCCESS` | session은 닫히지만 `known_secrets`는 유지된다. |
| 7 | final `StartSession NOT_AUTHORIZED`, HostChallenge=`a5a1c7fc...` | final challenge가 known secret과 같으므로 expected status는 `SUCCESS`다. `_start_session_inconsistent()`가 `challenge in known_secrets and status != success`로 `fail`. FSM도 `START_RW_ADMIN_SID -> SUCCESS` mismatch로 `fail`. |

### tc14 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP, HostChallenge 없음 | active session 생성, `authenticated=False`, `session_write=True`. |
| 2 | prefix `Get C_PIN SUCCESS`, uid `84 02`, Cellblock `3..3` | ProtocolState에는 저장하지 않는다. FSM은 MSID/C_PIN read success path를 따라간다. |
| 3 | prefix `EndSession SUCCESS` | session clear. secret state는 아직 없음. |
| 4 | prefix `StartSession SUCCESS`, HostChallenge=`3P5ADJ...`, HSA=SID | 인증된 Admin session으로 보고 `authenticated=True`. |
| 5 | prefix `Set C_PIN SUCCESS`, Values[3]=`3e06061d...` | `_advance_state()`가 `known_secrets`에 `3e06061d...`를 넣고 C_PIN object field도 저장한다. |
| 6 | prefix `EndSession SUCCESS` | session clear. `known_secrets`는 유지. |
| 7 | prefix `StartSession SUCCESS`, HostChallenge=`3e06061d...` | known secret과 맞는 challenge라 인증 성공 prefix로 state가 이어진다. |
| 8 | prefix `Set C_PIN SUCCESS`, Values[3]=`f620e538...` | 두 번째 C_PIN secret을 `known_secrets`와 `object_fields`에 저장한다. |
| 9 | prefix `EndSession SUCCESS` | session clear. known secret 집합은 유지된다. |
| 10 | final `StartSession SUCCESS`, HostChallenge=`aaaaaaaa...` | final challenge가 known secret 집합에 없으므로 expected status는 `NOT_AUTHORIZED`다. 실제 `SUCCESS`라 `_start_session_inconsistent()`가 `fail`. FSM도 `START_RW_ADMIN_SID_WRONG_PW -> NOT_AUTHORIZED` mismatch로 `fail`. |

### tc15 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP, HostChallenge 없음 | active session 생성, `authenticated=False`, `session_write=True`. |
| 2 | prefix `Get C_PIN SUCCESS`, uid `84 02`, Cellblock `3..3` | ProtocolState 저장 없음. FSM은 C_PIN read success path를 따라간다. |
| 3 | prefix `EndSession SUCCESS` | session clear. |
| 4 | prefix `StartSession SUCCESS`, HostChallenge=`3P5ADJ...`, HSA=SID | 인증된 Admin session으로 갱신. |
| 5 | prefix `Set C_PIN SUCCESS`, Values[3]=`3e06061d...` | `known_secrets`와 C_PIN object field 저장. |
| 6 | prefix `EndSession SUCCESS` | session clear, secret 유지. |
| 7 | prefix `StartSession SUCCESS`, HostChallenge=`3e06061d...` | known secret 기반 authenticated session이 된다. |
| 8 | prefix `Get SP SUCCESS`, valid-looking SP uid `00 00 02 05 00 00 00 02`, column 6 -> 8 | ProtocolState에는 별도 저장하지 않는다. FSM은 SP/activation 준비 path의 evidence로 사용한다. |
| 9 | final `Activate SUCCESS`, SP uid `00 00 01 05 00 00 00 04` | `_activate_target_invalid()`가 uid가 `00000205`로 시작하지 않는다고 판단한다. expected `INVALID_PARAMETER`, actual `SUCCESS`; `PRECONDITION_EXPECTED_ERROR`로 `fail`. FSM은 low-confidence unknown이라 base `fail` 유지. |

### tc16 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP, no HostChallenge | active session 생성, unauthenticated. |
| 2 | prefix `Get C_PIN SUCCESS`, uid `84 02`, column 3 | ProtocolState 저장 없음. FSM C_PIN read path. |
| 3 | prefix `EndSession SUCCESS` | session clear. |
| 4 | prefix `StartSession SUCCESS`, HostChallenge=`3P5ADJ...` | authenticated Admin session. |
| 5 | prefix `Set C_PIN SUCCESS`, Values[3]=`3e06061d...` | `known_secrets`와 C_PIN field 저장. |
| 6 | prefix `EndSession SUCCESS` | session clear, secret 유지. |
| 7 | prefix `StartSession SUCCESS`, HostChallenge=`3e06061d...` | authenticated Admin session. |
| 8 | prefix `Get SP SUCCESS`, SP column 6 -> 8 | ProtocolState 저장 없음. FSM activation 관련 success path. |
| 9 | prefix `Activate SUCCESS`, SP uid `00 00 02 05 00 00 00 02` | `_advance_state()`가 `activated_sps`에 compact invoking을 추가한다. FSM도 Locking SP activated path로 전진한다. |
| 10 | prefix `EndSession SUCCESS` | session clear. |
| 11 | prefix `StartSession SUCCESS`, Locking SP, no HostChallenge | active session 생성, no challenge라 `authenticated=False`. |
| 12 | prefix `Get LockingInfo SUCCESS`, column 4 -> `00000008` | ProtocolState 저장 없음. FSM은 LockingInfo read success를 본다. |
| 13 | prefix `EndSession SUCCESS` | session clear. |
| 14 | prefix `StartSession SUCCESS`, Locking SP, HostChallenge=`3e06061d...`, HSA=Admin1 | authenticated Locking session으로 갱신. |
| 15 | prefix `Get MBRControl SUCCESS`, columns 1..2 -> 0,0 | ProtocolState 저장 없음. final과 직접 충돌하지는 않지만 known object read path를 형성한다. |
| 16 | prefix `EndSession SUCCESS` | session clear. |
| 17 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 18 | prefix `Get Locking SUCCESS`, columns 3..8 -> zeros | ProtocolState 저장 없음. Locking object가 정상 read 가능한 shape임을 보여준다. |
| 19 | prefix `EndSession SUCCESS` | session clear. |
| 20 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | final Set 직전 active/authenticated session을 만든다. |
| 21 | final `Set Authority INVALID_PARAMETER`, uid `00 00 00 09 00 03 00 01`, Values[5]=1 | expected state error는 없다. `_known_field_access_expected_success()`가 `authority:5`를 반환한다. 성공해야 하는 Authority enable이 `INVALID_PARAMETER`라 `fail`. FSM은 possible success action을 보지만 confidence가 낮아 override하지 않는다. |

### tc17 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP, no HostChallenge | active session 생성, unauthenticated. |
| 2 | prefix `Get C_PIN SUCCESS`, uid `84 02`, column 3 | ProtocolState 저장 없음. FSM C_PIN read path. |
| 3 | prefix `EndSession SUCCESS` | session clear. |
| 4 | prefix `StartSession SUCCESS`, HostChallenge=`3P5ADJ...` | authenticated Admin session. |
| 5 | prefix `Set C_PIN SUCCESS`, SID C_PIN Values[3]=`3e06061d...` | `known_secrets`와 C_PIN field 저장. |
| 6 | prefix `EndSession SUCCESS` | session clear, secret 유지. |
| 7 | prefix `StartSession SUCCESS`, HostChallenge=`3e06061d...` | authenticated Admin session. |
| 8 | prefix `Get SP SUCCESS`, SP column 6 -> 8 | ProtocolState 저장 없음. FSM activation context. |
| 9 | prefix `Activate SUCCESS`, SP uid `00 00 02 05 00 00 00 02` | `activated_sps` 갱신. |
| 10 | prefix `EndSession SUCCESS` | session clear. |
| 11 | prefix `StartSession SUCCESS`, Locking SP, no HostChallenge | active session, unauthenticated. |
| 12 | prefix `Get LockingInfo SUCCESS`, column 4 -> `00000008` | ProtocolState 저장 없음. FSM LockingInfo read path. |
| 13 | prefix `EndSession SUCCESS` | session clear. |
| 14 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 15 | prefix `Get MBRControl SUCCESS`, columns 1..2 -> 0,0 | ProtocolState 저장 없음. |
| 16 | prefix `EndSession SUCCESS` | session clear. |
| 17 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 18 | prefix `Get Locking SUCCESS`, columns 3..8 | ProtocolState 저장 없음. |
| 19 | prefix `EndSession SUCCESS` | session clear. |
| 20 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 21 | prefix `Set Authority SUCCESS`, Values[5]=1 | `_advance_state()`가 Authority object field column 5를 저장한다. |
| 22 | prefix `EndSession SUCCESS` | session clear. |
| 23 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 24 | prefix `Set C_PIN SUCCESS`, User/Admin C_PIN Values[3]=`9dd74dd6...` | `_advance_state()`가 final challenge와 같은 secret을 `known_secrets`에 저장한다. |
| 25 | prefix `EndSession SUCCESS` | session clear, known secret 유지. |
| 26 | final `StartSession NOT_AUTHORIZED`, Locking SP, HSA=`0000000900030001`, HostChallenge=`9dd74dd6...` | final challenge가 record 24의 known secret과 같다. `_start_session_inconsistent()`가 known credential non-success로 `fail`. FSM은 low-confidence unknown이라 base `fail` 유지. |

### tc18 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP | active session 생성. |
| 2 | prefix `Get C_PIN SUCCESS`, column 3 | ProtocolState 저장 없음. |
| 3 | prefix `EndSession SUCCESS` | session clear. |
| 4 | prefix `StartSession SUCCESS`, HostChallenge=`3P5ADJ...` | authenticated Admin session. |
| 5 | prefix `Set C_PIN SUCCESS`, Values[3]=`3e06061d...` | `known_secrets`와 C_PIN field 저장. |
| 6 | prefix `EndSession SUCCESS` | session clear. |
| 7 | prefix `StartSession SUCCESS`, HostChallenge=`3e06061d...` | authenticated Admin session. |
| 8 | prefix `Get SP SUCCESS`, column 6 -> 8 | ProtocolState 저장 없음. |
| 9 | prefix `Activate SUCCESS`, valid Locking SP uid | `activated_sps` 갱신. |
| 10 | prefix `EndSession SUCCESS` | session clear. |
| 11 | prefix `StartSession SUCCESS`, Locking SP, no HostChallenge | active session, unauthenticated. |
| 12 | prefix `Get LockingInfo SUCCESS`, column 4 -> `00000008` | ProtocolState 저장 없음. |
| 13 | prefix `EndSession SUCCESS` | session clear. |
| 14 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 15 | prefix `Get MBRControl SUCCESS`, columns 1..2 -> 0,0 | ProtocolState 저장 없음. |
| 16 | prefix `EndSession SUCCESS` | session clear. |
| 17 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 18 | prefix `Get Locking SUCCESS`, columns 3..8 -> values returned | 같은 object/columns가 정상 read 가능한 shape임을 보여준다. |
| 19 | prefix `EndSession SUCCESS` | session clear. |
| 20 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | final Get 직전 active/authenticated session. |
| 21 | final `Get Locking INVALID_PARAMETER`, columns 3..8 | `_known_field_access_expected_success()`가 `locking:3,4,5,6,7,8`을 반환한다. 성공해야 하는 read가 `INVALID_PARAMETER`라 `fail`. FSM은 low-confidence unknown이라 override 없음. |

### tc19 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP | active session 생성. |
| 2 | prefix `Get C_PIN SUCCESS`, column 3 | ProtocolState 저장 없음. |
| 3 | prefix `EndSession SUCCESS` | session clear. |
| 4 | prefix `StartSession SUCCESS`, HostChallenge=`3P5ADJ...` | authenticated Admin session. |
| 5 | prefix `Set C_PIN SUCCESS`, Values[3]=`3e06061d...` | `known_secrets`와 C_PIN field 저장. |
| 6 | prefix `EndSession SUCCESS` | session clear. |
| 7 | prefix `StartSession SUCCESS`, HostChallenge=`3e06061d...` | authenticated Admin session. |
| 8 | prefix `Get SP SUCCESS`, column 6 -> 8 | ProtocolState 저장 없음. |
| 9 | prefix `Activate SUCCESS`, valid Locking SP uid | `activated_sps` 갱신. |
| 10 | prefix `EndSession SUCCESS` | session clear. |
| 11 | prefix `StartSession SUCCESS`, Locking SP, no HostChallenge | active Locking session. |
| 12 | prefix `Get LockingInfo SUCCESS`, column 4 -> `00000008` | ProtocolState 저장 없음. |
| 13 | prefix `EndSession SUCCESS` | session clear. |
| 14 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 15 | prefix `Get MBRControl SUCCESS`, columns 1..2 -> 0,0 | MBRControl columns 1,2가 정상 read 가능한 context다. |
| 16 | prefix `EndSession SUCCESS` | session clear. |
| 17 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 18 | prefix `Get Locking SUCCESS`, columns 3..8 | ProtocolState 저장 없음. |
| 19 | prefix `EndSession SUCCESS` | session clear. |
| 20 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 21 | prefix `Set MBRControl SUCCESS`, Values[2]=1 | `_advance_state()`가 MBRControl column 2를 `object_fields`에 저장한다. |
| 22 | prefix `EndSession SUCCESS` | session clear. |
| 23 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 24 | prefix `Set MBRControl SUCCESS`, Values[1]=1 | `_advance_state()`가 MBRControl column 1을 `object_fields`에 저장한다. |
| 25 | prefix `EndSession SUCCESS` | session clear. |
| 26 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | final Get 직전 active/authenticated session. |
| 27 | final `Get MBRControl FAIL`, columns 1..2 | `_known_field_access_expected_success()`가 `mbrcontrol:1,2`를 반환한다. 성공해야 하는 read가 `FAIL`이라 `fail`. FSM은 expected status를 만들지 못해 unknown. |

### tc20 Record별

| record | 원문 요약 | verifier effect |
|---:|---|---|
| 1 | prefix `StartSession SUCCESS`, Admin SP | active session 생성. |
| 2 | prefix `Get C_PIN SUCCESS`, column 3 | ProtocolState 저장 없음. |
| 3 | prefix `EndSession SUCCESS` | session clear. |
| 4 | prefix `StartSession SUCCESS`, HostChallenge=`3P5ADJ...` | authenticated Admin session. |
| 5 | prefix `Set C_PIN SUCCESS`, Values[3]=`3e06061d...` | `known_secrets`와 C_PIN field 저장. |
| 6 | prefix `EndSession SUCCESS` | session clear. |
| 7 | prefix `StartSession SUCCESS`, HostChallenge=`3e06061d...` | authenticated Admin session. |
| 8 | prefix `Get SP SUCCESS`, column 6 -> 8 | ProtocolState 저장 없음. |
| 9 | prefix `Activate SUCCESS`, valid Locking SP uid | `activated_sps` 갱신. |
| 10 | prefix `EndSession SUCCESS` | session clear. |
| 11 | prefix `StartSession SUCCESS`, Locking SP, no HostChallenge | active Locking session. |
| 12 | prefix `Get LockingInfo SUCCESS`, column 4 -> `00000008` | ProtocolState 저장 없음. |
| 13 | prefix `EndSession SUCCESS` | session clear. |
| 14 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 15 | prefix `Get MBRControl SUCCESS`, columns 1..2 -> 0,0 | ProtocolState 저장 없음. |
| 16 | prefix `EndSession SUCCESS` | session clear. |
| 17 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 18 | prefix `Get Locking SUCCESS`, columns 3..8 | ProtocolState 저장 없음. |
| 19 | prefix `EndSession SUCCESS` | session clear. |
| 20 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 21 | prefix `Set Locking SUCCESS`, Values[3,4,5,6,7,8]=initial range fields | `_advance_state()`가 Locking object fields 3,4,5,6,7,8을 저장한다. |
| 22 | prefix `EndSession SUCCESS` | session clear. |
| 23 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 24 | prefix `Get Locking SUCCESS`, column 10 -> key object UID | ProtocolState 저장 없음. FSM/key path context. |
| 25 | prefix `GenKey SUCCESS`, K_AES_256 | `_advance_state()`가 `generated_key_after_write=False`를 기록한다. 아직 write payload가 없기 때문이다. |
| 26 | prefix `EndSession SUCCESS` | session clear. |
| 27 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 28 | prefix `Set Locking SUCCESS`, Values[5]=1, Values[6]=1 | Locking object fields 5,6을 저장한다. |
| 29 | prefix `EndSession SUCCESS` | session clear. |
| 30 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 31 | prefix `Set Locking SUCCESS`, Values[7]=0, Values[8]=0 | Locking object fields 7,8을 저장한다. |
| 32 | prefix `EndSession SUCCESS` | session clear. |
| 33 | prefix data `Write`, LBA `80 ~ 87`, pattern `8E`, result `pass` | `_advance_state()`가 `written_payloads["80 ~ 87"]="8E"`를 저장하고 `generated_key_after_write=False`로 둔다. |
| 34 | prefix data `Read`, LBA `80 ~ 87`, result `Pattern 8E` | 기존 rulebase는 prefix Read payload를 상태 갱신에 쓰지 않는다. final stale 판단의 기준은 record 33 write payload다. |
| 35 | prefix `StartSession SUCCESS`, Locking SP, HSA=Admin1 | authenticated Locking session. |
| 36 | prefix `Get Locking SUCCESS`, column 10 -> key object UID | ProtocolState 저장 없음. |
| 37 | prefix `GenKey SUCCESS`, K_AES_256 | `written_payloads`가 이미 있으므로 `_advance_state()`가 `generated_key_after_write=True`를 만든다. |
| 38 | prefix `EndSession SUCCESS` | session clear. `written_payloads`와 `generated_key_after_write=True`는 유지된다. |
| 39 | final data `Read`, LBA `80 ~ 87`, result `8E` | `_read_payload_inconsistent()`가 final result가 stored write payload `8E`와 같고 `generated_key_after_write=True`임을 확인한다. GenKey 이후 old payload가 그대로 보여 stale read로 `fail`. |
