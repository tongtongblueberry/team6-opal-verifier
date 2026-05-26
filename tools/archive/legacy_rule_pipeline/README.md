# Legacy Rule Pipeline Archive

이 디렉터리는 현재 LLM-only manifest cycle에서 사용하지 않는 과거 pipeline 파일을 보관한다.

- 현재 active 학습 경로는 `tools/training/train_manifest_lora.py`와 `tools/training/train_manifest_full.py`이다.
- 현재 active 데이터 경로는 `tools/datagen/generate_long_shape_source.py`, `tools/analysis/build_supervised_manifest.py`, `tools/analysis/validate_manifest.py`이다.
- 현재 active 제출 entrypoint는 `src/solver.py`이다.
- `src/lora_solver.py`, `src/llm_solver.py`, `src/probe_solver.py`는 과거 helper solver이므로 이 archive 아래로 이동했다.
- 이 archive 안의 파일은 `/workspace/team6`, rule-id, 과거 public/rule 기반 실험을 포함할 수 있으므로 현재 제출 architecture나 학습 실행에 사용하지 않는다.
- 서버 작업 root는 `/workspace/sinjeongmin_opal_verifier`만 사용한다.
