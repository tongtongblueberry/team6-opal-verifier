<!-- 변경: Gate-A 감사 보고서 신규 작성. 이유: gen2 incremental 후보의 final_response 라벨 품질을 규칙 근거와 대조하기 위함. -->

# Gate-A 적대적 정성 감사 보고서

- 후보 파일: `runs/self_instruct/server_qwen_prod_gen2/combined_incremental/dedup_candidates.combined.namespaced.jsonl` 10건, JSONL 1-10행
- 규칙 파일: `docs/legacy_spec_rules.md` 707행, RULE 01-86
- 기준: final response만 라벨 대상이어야 하며, cited `source_span`이 final response의 조건과 기대 상태를 직접 지지해야 한다. 세션/auth/lifecycle/object state가 후보 내부에서 불일치하면 거부한다.

## 요약

| 결정 | 건수 | sample_id |
|---|---:|---|
| ACCEPT | 2 | `active::self-instruct-gen-00008-cand-00`, `active::self-instruct-gen-00020-cand-00` |
| REJECT | 7 | `active::self-instruct-gen-00002-cand-00`, `active::self-instruct-gen-00003-cand-00`, `active::self-instruct-gen-00004-cand-00`, `active::self-instruct-gen-00009-cand-00`, `active::self-instruct-gen-00012-cand-00`, `active::self-instruct-gen-00017-cand-00`, `active::self-instruct-gen-00021-cand-00` |
| UNCERTAIN | 1 | `active::self-instruct-gen-00000-cand-00` |

## 후보별 판정

### 1. `active::self-instruct-gen-00000-cand-00` - UNCERTAIN

[Original Text/Data] → 후보 1행: final target은 record 1 `Get`, final response는 `SUCCESS` 및 `["Column1Value", "Column2Value"]`; cited span은 RULE 20, `docs/legacy_spec_rules.md:151-156`, "Column name-value pairs SHALL be returned in the order listed in the Column table".  
[Exact Interpretation] → RULE 20은 컬럼 name-value pair의 순서를 검증하지만, 후보 final response에는 컬럼 식별자나 Column table 순서 근거가 없다. 같은 record의 Cellblock은 `startColumn: 1`, `endColumn: 1`이다.  
[Detailed Explanation/Example] → 두 값이 올바른 컬럼 순서인지, 또는 단일 컬럼 요청에서 두 값 반환이 허용되는지 cited span만으로 판단할 수 없다. `pass`를 확정할 근거가 부족하므로 UNCERTAIN.

### 2. `active::self-instruct-gen-00002-cand-00` - REJECT

[Original Text/Data] → 후보 2행: final target은 record 5 `EndSession` `SUCCESS`; cited span은 RULE 27, `docs/legacy_spec_rules.md:204-209`, "Set method invoked without Values parameter" 및 `SUCCESS (no effect)`.  
[Exact Interpretation] → RULE 27은 `Set` method에 적용되며, final response인 `EndSession`에는 직접 적용되지 않는다.  
[Detailed Explanation/Example] → 후보의 `Set`은 record 4이고 final target은 record 5이다. final response가 sole label target이어야 한다는 조건을 위반하므로 `pass` 라벨은 거부한다.

### 3. `active::self-instruct-gen-00003-cand-00` - REJECT

[Original Text/Data] → 후보 3행: final target은 record 9 `StartSession`, final response는 `SP_BUSY`; 라벨은 `fail`; cited span은 RULE 04, `docs/legacy_spec_rules.md:31-36`, concurrent session conflict의 expected status `SP_BUSY (0x03)`.  
[Exact Interpretation] → cited span이 지지하는 expected status는 `SP_BUSY`이다. final response도 `SP_BUSY`이므로, 조건이 성립한다면 final response는 valid로 판정되어야 한다.  
[Detailed Explanation/Example] → 라벨 `fail`은 cited expected status와 충돌한다. 또한 같은 후보 안에서 record 0 이후 record 1 `StartSession`도 성공해 기존 concurrent-session 조건과 충돌한다. 라벨과 세션 상태가 모두 불안정하므로 REJECT.

### 4. `active::self-instruct-gen-00004-cand-00` - REJECT

[Original Text/Data] → 후보 4행: final target은 record 9 `EndSession` `SUCCESS`; cited span은 RULE 48, `docs/legacy_spec_rules.md:371-376`, `Activate` on Manufactured-Inactive SP의 `SUCCESS; LifeCycleState changes to Manufactured`.  
[Exact Interpretation] → RULE 48은 `Activate` 및 lifecycle transition을 검증한다. final response는 `Activate`가 아니라 `EndSession`이다.  
[Detailed Explanation/Example] → 후보의 `Activate`는 record 8이고, final target은 record 9이다. 또한 final response에서 Manufactured-Inactive에서 Manufactured로의 상태 전이가 확인되지 않는다. final-response grounding 실패로 REJECT.

### 5. `active::self-instruct-gen-00008-cand-00` - ACCEPT

[Original Text/Data] → 후보 5행: final target은 record 8 `Properties`, final response는 `SUCCESS` 및 `{"MaxComPacketSize": 2500}`; cited span은 RULE 79, `docs/legacy_spec_rules.md:616-621`, `MaxComPacketSize >= 2048`.  
[Exact Interpretation] → final method가 cited rule의 method/condition과 일치하고, 반환값 2500은 최소값 2048 이상이다.  
[Detailed Explanation/Example] → RULE 79의 expected status는 "Properties method returns value >= 2048"이고, 후보 final response가 이를 직접 만족한다. `pass` 라벨은 plausible하므로 ACCEPT.

### 6. `active::self-instruct-gen-00009-cand-00` - REJECT

[Original Text/Data] → 후보 6행: final target은 record 9 `Read`, final response는 `INVALID_PARAMETER`; cited span은 RULE 79, `docs/legacy_spec_rules.md:616-621`, `Properties`의 `MaxComPacketSize >= 2048`.  
[Exact Interpretation] → RULE 79는 `Read` method나 `INVALID_PARAMETER`를 지지하지 않는다.  
[Detailed Explanation/Example] → cited span은 Properties capability value 검증 규칙이다. final response가 `Read`이므로 condition/expected status가 완전히 불일치한다. `fail` 라벨의 근거가 source span에서 나오지 않아 REJECT.

### 7. `active::self-instruct-gen-00012-cand-00` - REJECT

[Original Text/Data] → 후보 7행: final target은 record 6 `Set`, final response는 `NOT_AUTHORIZED`; cited span은 RULE 02, `docs/legacy_spec_rules.md:17-22`, AccessControl row 부재 또는 ACL 불충족 시 `NOT_AUTHORIZED`.  
[Exact Interpretation] → status 자체는 RULE 02 expected status와 맞지만, 후보 안에 AccessControl row 부재나 ACL 불충족을 입증하는 데이터가 없다.  
[Detailed Explanation/Example] → record 5에서 `HostSessionID: H0001`의 `EndSession`이 성공한 직후 record 6에서 같은 `H0001`로 `Set`을 수행한다. final response의 세션 상태가 내부적으로 불일치하고, cited ACL 조건도 입증되지 않는다. REJECT.

### 8. `active::self-instruct-gen-00017-cand-00` - REJECT

[Original Text/Data] → 후보 8행: final target은 record 19 `Get`, final response는 `SUCCESS` 및 empty list; cited spans는 RULE 18 `docs/legacy_spec_rules.md:137-142`와 RULE 01 `docs/legacy_spec_rules.md:10-15`.  
[Exact Interpretation] → RULE 18은 ACL이 허용하지 않는 cells를 결과에서 omit하는 경우를 지지하지만, 후보 final record에는 restricted cell, object, ACL 상태가 제시되지 않는다.  
[Detailed Explanation/Example] → record 18에서 `EndSession`이 성공한 뒤 record 19가 같은 `HostSessionID: H0001`로 `Get`을 수행한다. final response의 세션 상태가 내부적으로 불일치하며, empty result가 ACL omission인지 cited context로 판단할 수 없다. REJECT.

### 9. `active::self-instruct-gen-00020-cand-00` - ACCEPT

[Original Text/Data] → 후보 9행: final target은 record 1 `Get`, final response는 `SUCCESS` 및 `[{"column": 1, "value": "Value1"}]`; cited span은 RULE 20, `docs/legacy_spec_rules.md:151-156`.  
[Exact Interpretation] → RULE 20은 Get RowValues의 Column table order를 요구한다. 단일 컬럼 반환은 순서 위반이 없다.  
[Detailed Explanation/Example] → final response가 cited method와 일치하고, 반환 구조가 컬럼-값 pair를 포함한다. 라벨 `pass`는 source span으로 직접 지지 가능하므로 ACCEPT.

### 10. `active::self-instruct-gen-00021-cand-00` - REJECT

[Original Text/Data] → 후보 10행: final target은 record 1 `Get`, final response는 `SUCCESS` 및 `["unauthorized_column_data"]`; 라벨은 `fail`; cited span은 RULE 18, `docs/legacy_spec_rules.md:137-142`, unauthorized columns returned이면 fail.  
[Exact Interpretation] → RULE 18은 unauthorized column 반환을 fail로 볼 수 있지만, 후보에는 해당 값이 실제 unauthorized column임을 입증하는 object/ACL 근거가 없다.  
[Detailed Explanation/Example] → record 0 `StartSession`의 output은 `H0001`을 반환하지 않는데 record 1은 `HostSessionID: H0001`을 사용한다. final response의 세션 연결이 불명확하고, unauthorized 여부가 문자열 주장에만 의존한다. REJECT.
