# 현재 서버 운영 절차

- 최종 갱신: 2026-05-29 14:13:39 KST
<!-- Changed: record the current stopped gen3.1 server state before older model-validation history. -->
<!-- Why: server operators must not keep polling or restart the stopped Qwen Self-Instruct job by default. -->
- Current Self-Instruct generation state: stopped.
- Stopped server run:
  `runs/self_instruct/qwen_local_200_auth_statecheck_gen31_batch4_20260529_132800_KST`.
- Former server PIDs `120144` and `120148` are stopped.
- Final server raw count: `72 / 1000`.
- GPU after stop: `0 %, 0 MiB / 46068 MiB`.
- Local watcher `qwen_incremental_watch_gen31` is stopped.
- Local mirror: `runs/self_instruct/server_qwen_prod_gen31`.
- Local pending export: `data/local/gen3_pending`, `1` row, monitoring only.
- Canonical generated export: `data/local/gen3`, `0` rows.
- Do not train from `data/local/gen3_pending`; do not resume gen3.1 unchanged.
<!-- Changed: record RETRAIN-20 augmented-data queue blocker. -->
<!-- Why: server operators need the prepared run root and must not assume the experimental e30 comparison has metrics. -->
<!-- Changed: record DATA-REMEDIATION-2 completion in server recovery state. -->
<!-- Why: server operators must preserve the fixed manifest result without changing package/training eligibility. -->
<!-- Changed: record final pre-manifest-remediation-2 server/model/data state. -->
<!-- Why: server operators must stop polling the completed 4B retrieved queue and preserve DATA-RETRY/DATA-REMEDIATION-2 completed status while PACKAGE remains pending. -->
<!-- Changed: preserve the retrieved-context partial-run history while routing operators to the completed/no-go state. -->
<!-- Why: server operators must not poll stale retrieved queue targets or treat codex_agent_fallback artifacts as Gemini/provider data. -->
<!-- Changed: record final 4B QLoRA plain queue completion, no-go primary verdict, and next verified-code GPU slot rule. -->
<!-- Why: server operators must stop polling the finished plain queue and avoid opening unverified follow-up runs. -->
<!-- Changed: record 4B e20 seed47 completion, full e20 aggregate, and completed seed47 e10 state. -->
<!-- Why: server operators must not poll finished plain_seed47_e10 and must keep below-best 4B plain evidence out of package decisions. -->
<!-- Changed: retain completed 4B e30/e20 aggregate comparison against the 0.9B best. -->
<!-- Why: server operators need the 4B-vs-0.9B evidence and unchanged no-submit gates. -->
<!-- Changed: sync 12:34:18 KST epoch-grid poll, e10 retrieved generation complete no-go, and next-model-slot decision. -->
<!-- Why: server operators must check completed queue status, current best validation evidence, retrieval no-go evidence, and unchanged package/sample gates before submission decisions. -->
- 원칙: 제출/학습 architecture는 LLM-only다. rule engine, public label supervised 학습, legacy `/workspace/team6` 작업 root를 사용하지 않는다.
- SSH alias: `team6`
- 운영 root: `/workspace/sinjeongmin_opal_verifier`
- repo root: `/workspace/sinjeongmin_opal_verifier/repo`
- GitHub branch: `origin/sinjeongmin`
<!-- Changed: record cleanup classification for server operators. -->
<!-- Why: server cleanup must stay pending and must not delete remove-candidate files during status sync. -->
<!-- Changed: update server-visible model-validation artifact classification to the 10/10 split output. -->
<!-- Why: server workers must not restart training from the archived 16/4 split directory. -->
- docs/runs cleanup은 pending이다. active docs, research/spec docs, `runs/self_instruct/public20_baseline`, `runs/model_validation/public20_10_10_splits`는 keep이다. `runs/model_validation/public20_splits`는 16/4 archive-only evidence다. `server_access.md`는 secret-sensitive로 취급한다. `public20_trl_sft` derived JSONL은 remove-candidate pending이며 삭제하지 않는다. reports/plans는 archive 분류다.

## 접속

서버 접속은 한 번의 점검 단위에서 최소 10회 재시도한다. 비밀번호를 repo, 문서, shell script, command-line argument에 저장하지 않는다.

```bash
for i in $(seq 1 10); do
  printf 'SSH_RETRY_%02d_START %s KST\n' "$i" "$(TZ=Asia/Seoul date '+%F %T')"
  ssh -o BatchMode=yes \
      -o ControlMaster=no \
      -o ControlPath=none \
      -o ConnectTimeout=15 \
      -o ConnectionAttempts=1 \
      -o ServerAliveInterval=5 \
      -o ServerAliveCountMax=2 \
      team6 'echo connected'
  rc=$?
  printf 'SSH_RETRY_%02d_RC %s %s KST\n' "$i" "$rc" "$(TZ=Asia/Seoul date '+%F %T')"
  [ "$rc" -eq 0 ] && break
  sleep 5
done
```

## 서버 Repo 동기화

먼저 서버 repo가 우리 root인지 확인한다. `/workspace/team6`는 사용하지 않는다.

```bash
ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none team6 '
set -euo pipefail
cd /workspace/sinjeongmin_opal_verifier/repo
test "$PWD" = /workspace/sinjeongmin_opal_verifier/repo
git status --short --branch
git rev-parse HEAD
'
```

GitHub 접근이 가능하면 fast-forward만 허용한다.

```bash
ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none team6 '
set -euo pipefail
cd /workspace/sinjeongmin_opal_verifier/repo
test -z "$(git status --porcelain)"
git fetch origin sinjeongmin
expected="$(git rev-parse FETCH_HEAD)"
git merge-base --is-ancestor HEAD FETCH_HEAD
git merge --ff-only FETCH_HEAD
test "$(git rev-parse HEAD)" = "$expected"
'
```

GitHub 접근이 안 되면 로컬 bundle을 scp한 뒤 서버에서 fast-forward만 수행한다. bundle 파일명은 로컬에서 `git rev-parse --short HEAD`와 `git bundle verify`로 확인한 최신 파일을 사용한다.

```bash
scp /tmp/opal_cycle3_<short_head>_after_fca0652.bundle team6:/tmp/
ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none team6 '
set -euo pipefail
cd /workspace/sinjeongmin_opal_verifier/repo
test -z "$(git status --porcelain)"
git rev-parse --verify fca06523f66fdd8f4950da6c51d87e4efaa74b6d^{commit}
git fetch /tmp/opal_cycle3_<short_head>_after_fca0652.bundle HEAD
expected="$(git rev-parse FETCH_HEAD)"
git merge-base --is-ancestor HEAD FETCH_HEAD
git merge --ff-only FETCH_HEAD
test "$(git rev-parse HEAD)" = "$expected"
'
```

## 연결 회복 직후 확인 순서

<!-- Changed: add current stopped gen3.1 verification before historical queue checks. -->
<!-- Why: the newest server action was stopping Qwen generation, not launching another model-training queue. -->
현재 먼저 확인할 항목은 gen3.1 stopped state다.

```bash
ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none team6 '
cd /workspace/sinjeongmin_opal_verifier/repo
run=$(cat runs/self_instruct/latest_qwen_local_200_batch16.txt 2>/dev/null || true)
echo "RUN=$run"
ps -p 120144,120148 -o pid,ppid,etime,stat,args || true
test -n "$run" && wc -l "$run/raw_outputs.qwen_local.jsonl" "$run/generation_requests.jsonl"
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader
'
```

Expected stopped state: no `120144`/`120148` process rows, raw `72`, requests `1000`, GPU `0 %, 0 MiB, 46068 MiB`.

<!-- Changed: replace active poll target with completed 4B retrieved no-go evidence. -->
<!-- Why: current server recovery checks should preserve the completed retrieved result and route data work to DATA-REMEDIATION-2. -->
현재 확정 상태: corrected 0.9B full FT official TRL `10 train / 10 val` maxlen8192 queue는 2026-05-27 12:38:12 KST에 done이고, 4B plain-only TRL+PEFT/QLoRA queue도 `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1322_KST_public20_trl_10_10_4b_qlora_plain_maxlen8192`에서 done/no-go primary evidence다.
Completed 4B retrieved-context run root는 `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1701_KST_public20_trl_10_10_4b_qlora_retrieved_maxlen8192`다.
2026-05-27 20:24:16 KST 기준 queue done. e30 generation aggregate acc `0.6667`, macro-F1 `0.6652`; e20 generation aggregate acc `0.5667`, macro-F1 `0.5662`; e10 generation/logprob aggregate acc `0.5333`, macro-F1 `0.5313`.
e30/e20 logprob had OOMs. 4B retrieved is no-go primary; 0.9B e30 plain remains current best with acc `0.8000`, macro-F1 `0.7964`.
Completed plain queue reference: 2026-05-27 16:43:25 KST 기준 queue pid `361733`, alive `no`, queue_state=`done`, current_job=`plain_seed47_e10`; queue log says `plain_seed47_e10` done and `QUEUE_DONE` at `2026-05-27 16:17:05 KST`; GPU idle `0/46068 MiB`, util `0%`.
model id는 `Qwen/Qwen3.5-4B`이며 이전 4B adapter config와 server HF check로 확인했다. HF sha는 `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`다.
training stack은 TRL `SFTTrainer` + PEFT LoRA + bitsandbytes 4bit이며 trainable params는 `155,975,680 / 2,746,069,504 (5.68%)`다.
4B e10 seed metrics: seed11 acc `0.6000`, macro-F1 `0.5833`, fail/pass `0.8000/0.4000`, `TP=4 TN=2 FP=3 FN=1 INVALID=0`, eval_loss `0.7727`, `p_fail` min/max/mean `0.0158/0.9996/0.6944`; seed29 acc `0.8000`, macro-F1 `0.7917`, fail/pass `0.6000/1.0000`, `TP=3 TN=5 FP=0 FN=2 INVALID=0`, eval_loss `0.3758`, `p_fail` `0.0374/0.8938/0.3274`; seed47 acc `0.8000`, macro-F1 `0.7917`, fail/pass `0.6000/1.0000`, `TP=3 TN=5 FP=0 FN=2 INVALID=0`, eval_loss `0.6132`, `p_fail` `0.0123/0.9975/0.3458`.
4B e10 3-seed aggregate는 acc `0.7333`, macro-F1 `0.7321`, fail/pass `0.6667/0.8000`, `TP=10 TN=12 FP=3 FN=5 INVALID=0`이다.
4B e20 aggregate and e30 aggregate were identical: acc `0.7667`, macro-F1 `0.7643`, fail/pass `0.6667/0.8667`, `TP=10 TN=13 FP=2 FN=5`.
0.9B e30 plain best remains better: acc `0.8000`, macro-F1 `0.7964`, fail/pass `0.6667/0.9333`, `TP=10 TN=14 FP=1 FN=5`.
Decision: 4B QLoRA plain is complete and becomes `no-go as primary / auxiliary evidence only` unless later packaging constraints force fallback; it does not beat 0.9B e30 plain best.
failure scan은 `NaN`, `OOM`, `Traceback`, `Killed`, `RuntimeError`, `Exception` 없이 clean이다.
preflight는 `bitsandbytes==0.49.2`, `trl==1.5.0`, `peft==0.19.1`, `transformers==5.8.1`, `SFTConfig_completion_only_loss=True`, `TRL_get_kbit_device_map=True`, `max_length=8192`, `peft_enabled=True`, `quantization_enabled=True`, `min_shifted_valid_completion_label_count=1`로 통과했다.
job order는 plain `seed11/29/47` e30, e20, e10 complete이고 dataset은 `runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_{seed}`만 사용했다. train/eval batch size는 `1`, gradient accumulation은 `8`, generation/logprob eval은 `--max-length 8192`, logprob 뒤 `p_fail` sidecar를 생성했다.
기존 0545 queue `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft`는 training `--max-length 4096`으로 확인되어 no-go/reference only이며, 2026-05-27 07:12:11 KST에 queue pid `318407`을 stop했다.
stop marker는 `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft/status/stopped_for_corrected_maxlen8192_20260527_071211_KST.txt`다.
old 4096 queue의 `eval_loss NaN`은 이 stopped no-go/reference queue 범위에만 해당하며 corrected maxlen8192 queue 판단에는 적용하지 않는다.
completed 0.9B run root는 `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0716_KST_public20_trl_10_10_09b_fullft_maxlen8192`다.
2026-05-27 13:17:28 KST 확인 기준 corrected queue pid `328009`은 dead, queue state는 `done`, final `retrieved_seed47_e10` status도 `done`이다. 4B queue 시작 전 GPU는 `0 MiB / 0%` idle이었다.
corrected e20 plain/retrieved aggregate의 class metrics는 동일하다. acc `0.7666666667`, aggregate macro-F1 `0.7643097643`, fail/pass recall `0.6666666667/0.8666666667`, pooled confusion `TP=10 TN=13 FP=2 FN=5`이며 retrieved context는 class decision을 개선하지 않았다.
`retrieved_seed47_e20` overfit signal은 best eval_loss `0.2693` at epoch `10`, final eval_loss `1.8281660079956055`다.
current best validation evidence는 e30 plain aggregate complete 결과다. acc `0.8000`, aggregate macro-F1 `0.7964`, fail/pass recall `0.6667/0.9333`, pooled confusion `TP=10 TN=14 FP=1 FN=5`이다.
e30 plain delta는 e20 plain/retrieved aggregate 대비 acc `+0.0333`, aggregate macro-F1 `+0.0321`, pass recall `+0.0667`, fail recall unchanged로 modest improvement에 그친다.
e30 plain still overfit risk가 남아 있다. `plain_seed47_e30` loss는 final eval_loss `1.975`, best epoch `5` eval_loss `0.4341`이고, `plain_seed29_e30` loss는 final eval_loss `3.628`, best eval_loss `0.392`다.
e10 plain aggregate complete 결과는 secondary evidence다. acc `0.7667`, aggregate macro-F1 `0.7664`, fail/pass recall `0.7333/0.8000`, pooled confusion `TP=11 TN=12 FP=3 FN=4`이다. fail recall은 e30 plain보다 높지만 acc, macro-F1, pass recall은 e30 plain보다 낮다.
e5 plain acc는 `0.6667`이고 e5 retrieved acc는 `0.5000`이다.
e30 retrieved complete 결과는 acc `0.7667`, aggregate macro-F1 `0.7600`, mean seed macro-F1 `0.7601`, fail/pass recall `0.6/0.9333`, pooled confusion `TP=9 TN=14 FP=1 FN=6 INVALID=0`이다.
e30 retrieved는 e30 plain 대비 acc `-0.0333`, macro-F1 `-0.0364`, fail recall `-0.0667`, FN `+1`로 worse이며 retrieval e30 no-go evidence다.
e10 retrieved generation/logprob complete aggregate 결과는 acc `0.4667`, aggregate macro-F1 `0.4570`, fail/pass recall `0.3333/0.6000`, pooled confusion `TP=5 TN=9 FP=6 FN=10`으로 no-go다.
retrieval no-go evidence는 e20 no gain, e30 worse, e5 weak, e10 generation weak다.
failure scan은 clean except lowercase config key다.
queue order는 `e20`, `e30`, `e5`, `e10` block 순서이고 각 block은 plain seeds `11/29/47` 뒤 retrieved seeds `11/29/47` 순서다.
model은 `Qwen/Qwen3.5-0.8B`, full FT only, PEFT/LoRA disabled, 4bit disabled다. 다음 model slot은 queue 종료와 slot free 확인 뒤에만 4B TRL+PEFT/QLoRA로 연다.
training/generation/logprob 모두 `--max-length 8192`를 명시하며 logprob sidecar `p_fail` JSON을 생성한다.
help gate는 세 스크립트 모두 `--max-length` 지원을 확인했고, training dry-run plan은 default/configured/SFT `max_length=8192`, `completion_only_loss=True`, PEFT/quantization disabled다.
6개 plain/retrieved dataset tokenizer preflight는 모두 `checked_rows=20`, `min_shifted_valid_completion_label_count=1`로 통과했다.
4B plain TRL+PEFT/QLoRA는 verified TRL/PEFT/bitsandbytes path, `max_length` support, dataset/tokenizer preflight를 확인한 뒤 완료됐고 no-go primary / auxiliary evidence only다.
<!-- Changed: replace manifest-selected subset mismatch with DATA-REMEDIATION-2 fixed result. -->
<!-- Why: server recovery checks need the current data-gate state, not the pre-fix blocker. -->
Targeted schedule fallback smoke generated all `40` fallback candidates from `40` targets, labels `pass=20/fail=20`, record_count mean `16.4`. It passed parse `40/0`, dedup `40/0`, judge `40/0`, Gate A qualitative accepted `40/0`, accepted-pool Gate B with record_count mean delta `0.0`, and old Gate C `33/33`.
Old length balance selected `33/40`, label `fail=16/pass=17`, train `fail=12/pass=11`, length JSD `0.074814 <= 0.08`, and validation passed, but Gate B still had `record_count_mean_difference`: selected subset mean/max `13.7576/28` vs accepted/public mean/max `16.4/39`.
DATA-REMEDIATION-2 root cause was a length-bin-only JSD selector dropping high-depth rows `22,24,25,25,28,39,39`. The fix is optional `--preserve-record-count-distribution` in `tools/analysis/build_supervised_manifest.py`, default behavior unchanged, with tests added in `tests/test_build_supervised_manifest.py`.
New artifact `runs/self_instruct/targeted_schedule_20260527_192440_KST/manifest.record_count_preserved.codex_agent_fallback.jsonl` selected `20` rows, labels `fail=10/pass=10`, splits train `14` `fail=7/pass=7`, hidden `4` `fail=2/pass=2`, calibration `2` `fail=1/pass=1`, record_count min/median/mean/max `1/17.5/16.4/39`, length JSD `0.078355`; manifest validation passed, Gate B passed with `no_go_warnings=[]`, Gate C `20/20` passed.
Sample/training remains `false` due fallback provenance not provider/Gemini, incomplete ablations `200/500/1000/2000/4000`, and no Gate D/package/training. DATA-RETRY completed with partial improvement/no sample; DATA-REMEDIATION-2 completed; PACKAGE pending; DOC-SYNC in progress until this edit completes.
<!-- Changed: record the current local 200-row generated dataset bundle. -->
<!-- Why: server/data operators need the exact consolidated path and strict gate summary before any retraining decision. -->
LOCAL-GEN-200 completed locally at `data/local/gen/manifest.jsonl`, source root `runs/self_instruct/local_gen_strict_20260528_004842_KST`, count `200`, labels `fail=100/pass=100`, splits `train=140/hidden=40/calibration=20`, provenance `repo_local_structured_builder`, `provider_backed=false`. Gates passed: parse `200/0`, Self-Instruct `domain_text` dedup `200/0`, judge `200/0`, Gate A invariant `200/0`, sampled qualitative state-transition audit `12/12`, Gate B `no_go_warnings=[]`, manifest validation `overall_gate_passed=true`, length JSD `0.0`, record_count mean `16.4`, Gate C `200/200`, and model input smoke loaded `140` train rows in full/LoRA loaders.
package/submission no-go, package gate도 아직 통과하지 않았다. 이전 4B QLoRA interrupted run root
`/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0434_KST_public20_candidate_training` 결과는 후보로 쓰지 않는다.

1. `/workspace/sinjeongmin_opal_verifier/repo`의 `git status --short --branch`, `git rev-parse HEAD`.
<!-- Changed: replace old baseline-resume checklist with stopped-queue/no-trust checks. -->
<!-- Why: prior generated-data-based runs and interrupted queue outputs are not current candidates. -->
2. completed 4B retrieved run root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1701_KST_public20_trl_10_10_4b_qlora_retrieved_maxlen8192`의 done/no-go status와 OOM 기록을 보존한다. 2026-05-27 20:24:16 KST 기준 4B retrieved is no-go primary and 0.9B e30 plain remains current best. package/runtime gate 전 package/submission 판단 금지.
3. GPU 상태: `nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader`.
4. v4/v4.1 데이터 제외 확인:
   - `docs/archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md` 기준으로 v4/v4.1 raw/manifest는 학습과 제출 판단에서 제외한다.
<!-- Changed: point restart checks at the implemented active 10/10 split artifacts. -->
<!-- Why: server workers must preserve the active 10/10 split basis while checking the already-started 0.9B full FT queue. -->
5. public20-only model validation 재시작은 `runs/model_validation/public20_10_10_splits` 기준으로만 진행한다. seed `11`, `29`, `47` 각각 `train=10`, `val=10`, train/val label `fail=5/pass=5`이며 public20 `test` split은 없다. 기존 `runs/model_validation/public20_splits` 16/4 결과는 archive evidence only다.
6. 현재 baseline GPU train/eval queue는 completed 상태다. RETRAIN-20 experimental e30 queue root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_2316_KST_retrain20_augmented20_09b_fullft_maxlen8192`는 2026-05-27 23:16 KST에 GPU 점유로 training 전 blocked됐고, GPU idle 확인 후 2026-05-27 23:36 KST에 retry됐다. Retry는 seed `11/29/47` 모두 `train_failed rc=2`로 끝났다. 원인은 generated train rows `00038`, `00039`가 `max_length=8192` completion-label preflight를 실패한 것이다. DATA-REMEDIATION-2 manifest selection distribution preservation은 completed지만 fallback provenance, incomplete ablations, and missing Gate D/package/training 때문에 sample/training/package 판단은 바꾸지 않는다.
<!-- Changed: record worker-reported focused verification results for server restart context. -->
<!-- Why: server operators should know the latest local split/Self-Instruct checks passed before retraining. -->
7. worker-reported verification: split builder `6 tests OK`, self_instruct `23 tests OK`, worker `git diff --check OK`.
8. GPU train/eval checklist는 completed다. 추가 model slot은 package/data gate 확인 전에는 열지 않는다.
9. package `<12GB`, `check_submit_package.py`, offline first-forward smoke가 모두 통과할 때만 leaderboard 제출을 검토한다.

## 제출 판단

<!-- Changed: add no-trust data, revised split, interrupted-queue, and project.pdf package gates. -->
<!-- Why: submission decisions must exclude untrusted generated data and interrupted training evidence. -->
<!-- Changed: record accepted leaderboard submission from the 0.9B e30 plain full-FT package. -->
<!-- Why: server operators need the package path, gate result, and submit IDs before considering retries. -->
2026-05-27 23:41 KST submission completed.
Selected artifact:
`/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0716_KST_public20_trl_10_10_09b_fullft_maxlen8192/models/plain_seed11_e30`.
Package:
`/workspace/sinjeongmin_opal_verifier/ops/submission_worker_20260527_2317_KST_leaderboard_seed11_e30/submissions/submit-plain_seed11_e30`.
Package gates passed: size `3432155481` bytes `<12GB`, `check_submit_package.py`, no-rule scan,
and `runtime_smoke_submit_package.py --offline --first-forward`.
Submit accepted Job ID `668`, Submission ID `5bcc1bdda5e347d499aa99adbb2ba2ee`,
Job Name `09b-e30-plain-seed11-fullft-20260527`.
현재 leaderboard 제출은 no-go다. 4B QLoRA plain은 e10/e20/e30까지 complete지만 0.9B e30 plain best보다 낮아 `no-go as primary / auxiliary evidence only`다. 4B QLoRA+retrieval도 2026-05-27 20:24:16 KST 기준 done/no-go primary다. 제출하려면 다음 evidence가 필요하다.

- 기존 generated synthetic data가 학습/accepted sample에서 제외되고 감사/격리 대상으로만 남았다는 기록.
- DATA-GEN provider data no-go가 해소되고 공개 sample 1개가 모든 검증을 통과했다는 기록. 현재 server Gemini check at `team6` showed `GEMINI_API_KEY=false`, `GOOGLE_API_KEY=false`; no real Gemini raw output was created. `codex_agent_fallback` artifacts are no-go and `docs/samples/self_instruct_sample.md` remains absent/no-go.
- public20-only model validation이 `10 train / 10 val` 기준으로 재검증됐다는 기록. 기존 `16 train / 4 val` 결과는 archive evidence only다.
<!-- Changed: add remaining TRL conversion/GPU restart evidence requirement. -->
<!-- Why: split builder completion alone is not a trained candidate. -->
<!-- Changed: replace e10 running requirement with final 4B plain completion evidence. -->
<!-- Why: current best is 0.9B e30 plain, completed 4B plain is lower, and package/runtime/data sample gates remain blocked. -->
- corrected 0.9B full FT official TRL 10/10 maxlen8192 queue는 done이고 current best validation evidence는 e30 plain complete 결과로 acc `0.8000`, aggregate macro-F1 `0.7964`, fail/pass recall `0.6667/0.9333`, pooled confusion `TP=10 TN=14 FP=1 FN=5`이다. 4B QLoRA plain은 complete/no-go primary evidence다. 4B retrieved-context run root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_1701_KST_public20_trl_10_10_4b_qlora_retrieved_maxlen8192`는 done/no-go primary다: e30 generation aggregate acc `0.6667`, macro-F1 `0.6652`; e20 generation aggregate acc `0.5667`, macro-F1 `0.5662`; e10 generation/logprob aggregate acc `0.5333`, macro-F1 `0.5313`; e30/e20 logprob had OOMs. package 판단, package `<12GB`, offline first-forward smoke는 아직 없으며 package/submission no-go다.
- DATA-RETRY completed with partial improvement/no sample; DATA-REMEDIATION-2 manifest selection distribution preservation completed; PACKAGE pending; DOC-SYNC in progress until this edit completes.
- 중단된 4B QLoRA queue 결과를 후보로 쓰지 않았다는 기록.
- required submission files가 project.pdf 기준으로 재검증됐다는 기록: `setup.sh`, `pyproject.toml`, `uv.lock`, `src/solver.py`, `src/__init__.py` 등.
- 새 학습 artifact 또는 평가 대상 artifact의 완료 상태.
- calibration/hidden 평가 결과와 threshold 결정 근거.
- package 크기 `<12GB`.
- `tools/eval/check_submit_package.py` 통과.
- `tools/eval/runtime_smoke_submit_package.py --offline --first-forward` 통과.
- 기존 leaderboard 결과 대비 왜 지금 제출해야 하는지에 대한 기록.
