"""LoRA 어댑터 가중치 평균(Model Soup) 병합 스크립트.

Changed: 동일 아키텍처(rank, alpha)의 여러 LoRA 어댑터 가중치를 평균하여 단일 어댑터 생성.
Why: 개별 어댑터마다 다른 데이터/에폭에서 학습 → 가중 평균으로 분산 감소 및 일반화 향상.
     추가 학습 불필요(inference-time improvement).

사용법:
  python tools/eval/merge_adapters.py \
      --adapters /path/to/adapter1 /path/to/adapter2 /path/to/adapter3 \
      --output /path/to/merged/ \
      --weights 0.3,0.5,0.2
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Changed: 프로젝트 루트를 sys.path에 추가 — 서버에서도 import 가능하도록.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_adapter_weights(adapter_path: str) -> dict:
    """어댑터 가중치 로드 (safetensors 우선, bin 폴백).

    Changed: safetensors와 pytorch_model.bin 둘 다 지원.
    Why: 어댑터 저장 형식이 학습 설정에 따라 다를 수 있음.
    """
    from safetensors.torch import load_file

    safetensors_path = os.path.join(adapter_path, "adapter_model.safetensors")
    bin_path = os.path.join(adapter_path, "adapter_model.bin")

    if os.path.exists(safetensors_path):
        print(f"[로드] safetensors: {safetensors_path}")
        return load_file(safetensors_path)
    elif os.path.exists(bin_path):
        import torch
        print(f"[로드] bin: {bin_path}")
        return torch.load(bin_path, map_location="cpu")
    else:
        raise FileNotFoundError(
            f"어댑터 가중치 파일을 찾을 수 없음: {adapter_path}\n"
            f"  확인한 경로: {safetensors_path}, {bin_path}"
        )


def load_adapter_config(adapter_path: str) -> dict:
    """adapter_config.json 로드."""
    config_path = os.path.join(adapter_path, "adapter_config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"adapter_config.json 없음: {config_path}")
    with open(config_path, "r") as f:
        return json.load(f)


def validate_configs(configs: list[dict], adapter_paths: list[str]) -> None:
    """모든 어댑터의 설정이 호환되는지 검증.

    Changed: rank(r), alpha, target_modules가 일치해야 병합 가능.
    Why: 다른 아키텍처의 가중치를 평균하면 의미 없는 결과.
    """
    ref = configs[0]
    ref_r = ref.get("r", ref.get("rank"))
    ref_alpha = ref.get("lora_alpha")
    ref_targets = sorted(ref.get("target_modules", []))

    for i, cfg in enumerate(configs[1:], 1):
        cur_r = cfg.get("r", cfg.get("rank"))
        cur_alpha = cfg.get("lora_alpha")
        cur_targets = sorted(cfg.get("target_modules", []))

        errors = []
        if cur_r != ref_r:
            errors.append(f"rank 불일치: {ref_r} vs {cur_r}")
        if cur_alpha != ref_alpha:
            errors.append(f"alpha 불일치: {ref_alpha} vs {cur_alpha}")
        if cur_targets != ref_targets:
            errors.append(f"target_modules 불일치: {ref_targets} vs {cur_targets}")

        if errors:
            raise ValueError(
                f"어댑터 설정 불일치 (0: {adapter_paths[0]} vs {i}: {adapter_paths[i]}):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    print(f"[검증] 모든 어댑터 호환: r={ref_r}, alpha={ref_alpha}, "
          f"target_modules={ref_targets}")


def merge_weights(
    all_weights: list[dict],
    weights: list[float] | None = None,
) -> dict:
    """여러 어댑터의 가중치를 가중 평균으로 병합.

    Changed: 선택적 가중치 지정 — 성능 좋은 어댑터에 더 높은 비중.
    Why: 균등 평균보다 성능 기반 가중 평균이 효과적 (Wortsman et al., 2022).

    Args:
        all_weights: 어댑터별 가중치 딕셔너리 리스트
        weights: 어댑터별 가중치 (None이면 균등 분배)

    Returns:
        병합된 가중치 딕셔너리
    """
    import torch

    n = len(all_weights)
    if weights is None:
        weights = [1.0 / n] * n
    else:
        # Changed: 가중치 합이 1이 되도록 정규화.
        # Why: 임의 가중치 입력 시에도 올바른 평균 보장.
        total = sum(weights)
        weights = [w / total for w in weights]

    assert len(weights) == n, f"가중치 개수({len(weights)}) != 어댑터 개수({n})"

    # Changed: 첫 번째 어댑터의 키를 기준으로 병합.
    # Why: 모든 어댑터가 동일 아키텍처 → 동일 키 보유 (validate_configs에서 검증 완료).
    ref_keys = set(all_weights[0].keys())
    for i, w in enumerate(all_weights[1:], 1):
        cur_keys = set(w.keys())
        if cur_keys != ref_keys:
            missing = ref_keys - cur_keys
            extra = cur_keys - ref_keys
            print(f"[경고] 어댑터 {i} 키 불일치:")
            if missing:
                print(f"  누락: {missing}")
            if extra:
                print(f"  추가: {extra}")

    merged = {}
    for key in ref_keys:
        # Changed: 가중 합으로 병합 — GPU 메모리 절약을 위해 CPU에서 수행.
        # Why: 어댑터 가중치는 작아서 CPU로 충분.
        tensors = []
        for i, w in enumerate(all_weights):
            if key in w:
                tensors.append(w[key].float() * weights[i])
            else:
                print(f"[경고] 어댑터 {i}에 키 '{key}' 없음 — 0으로 대체")
                tensors.append(torch.zeros_like(all_weights[0][key]).float() * weights[i])

        merged[key] = sum(tensors).half()  # Changed: float16으로 저장 — 원본과 동일 dtype.

    return merged


def print_weight_stats(
    all_weights: list[dict],
    merged: dict,
    adapter_names: list[str],
) -> None:
    """각 어댑터와 병합 결과의 가중치 통계 출력.

    Changed: 레이어별 L2 norm, 평균, 표준편차 비교 테이블 출력.
    Why: 병합 품질 검증 — 너무 큰 차이 있으면 문제 가능.
    """
    import torch

    print("\n" + "=" * 80)
    print("가중치 통계 비교")
    print("=" * 80)

    # Changed: 대표적인 키 몇 개만 출력 (전체 출력하면 너무 길어짐).
    # Why: lora_A/lora_B 패턴만 확인하면 충분.
    sample_keys = sorted(merged.keys())[:10]

    header = f"{'Key (앞 60자)':<60}"
    for name in adapter_names:
        header += f" | {name[:12]:>12}"
    header += f" | {'Merged':>12}"
    print(header)
    print("-" * len(header))

    for key in sample_keys:
        row = f"{key[:60]:<60}"
        for w in all_weights:
            if key in w:
                norm = torch.norm(w[key].float()).item()
                row += f" | {norm:>12.4f}"
            else:
                row += f" | {'N/A':>12}"
        merged_norm = torch.norm(merged[key].float()).item()
        row += f" | {merged_norm:>12.4f}"
        print(row)

    # Changed: 전체 가중치의 총 L2 norm 비교.
    # Why: 전체적인 크기 변화 확인.
    print("\n전체 L2 norm:")
    for i, (name, w) in enumerate(zip(adapter_names, all_weights)):
        total_norm = sum(torch.norm(v.float()).item() ** 2 for v in w.values()) ** 0.5
        print(f"  {name}: {total_norm:.4f}")
    merged_total = sum(torch.norm(v.float()).item() ** 2 for v in merged.values()) ** 0.5
    print(f"  Merged: {merged_total:.4f}")

    # Changed: 어댑터 간 가중치 차이(L2 distance) 출력.
    # Why: 너무 다른 어댑터를 병합하면 효과 없음.
    print("\n어댑터 간 L2 거리:")
    for i in range(len(all_weights)):
        for j in range(i + 1, len(all_weights)):
            dist = 0.0
            common_keys = set(all_weights[i].keys()) & set(all_weights[j].keys())
            for key in common_keys:
                diff = all_weights[i][key].float() - all_weights[j][key].float()
                dist += torch.norm(diff).item() ** 2
            dist = dist ** 0.5
            print(f"  {adapter_names[i]} <-> {adapter_names[j]}: {dist:.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="LoRA 어댑터 가중 평균 병합 (Model Soup)"
    )
    parser.add_argument(
        "--adapters",
        nargs="+",
        required=True,
        help="병합할 어댑터 경로들 (2개 이상)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="병합된 어댑터 저장 경로",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="어댑터별 가중치 (쉼표 구분, 예: 0.3,0.5,0.2). 미지정 시 균등 분배.",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="가중치 통계 출력 생략",
    )
    args = parser.parse_args()

    # Changed: 가중치 파싱 및 검증.
    if args.weights:
        weight_list = [float(w) for w in args.weights.split(",")]
        if len(weight_list) != len(args.adapters):
            print(f"[오류] 가중치 개수({len(weight_list)}) != 어댑터 개수({len(args.adapters)})")
            sys.exit(1)
    else:
        weight_list = None

    # Changed: 모든 어댑터 경로 존재 확인.
    for path in args.adapters:
        if not os.path.exists(path):
            print(f"[오류] 어댑터 경로 없음: {path}")
            sys.exit(1)

    # 1. 설정 로드 및 호환성 검증
    print("=" * 60)
    print("Step 1: 어댑터 설정 검증")
    print("=" * 60)
    configs = [load_adapter_config(p) for p in args.adapters]
    validate_configs(configs, args.adapters)

    # 2. 가중치 로드
    print("\n" + "=" * 60)
    print("Step 2: 가중치 로드")
    print("=" * 60)
    all_weights = [load_adapter_weights(p) for p in args.adapters]

    adapter_names = [os.path.basename(os.path.dirname(p)) or os.path.basename(p)
                     for p in args.adapters]

    # Changed: 키 개수와 총 파라미터 수 출력.
    for i, (name, w) in enumerate(zip(adapter_names, all_weights)):
        n_params = sum(v.numel() for v in w.values())
        print(f"  [{name}] 키: {len(w)}, 파라미터: {n_params:,}")

    # 3. 병합
    print("\n" + "=" * 60)
    print("Step 3: 가중치 병합")
    print("=" * 60)
    if weight_list:
        total = sum(weight_list)
        norm_weights = [w / total for w in weight_list]
        for name, w in zip(adapter_names, norm_weights):
            print(f"  {name}: {w:.4f}")
    else:
        n = len(args.adapters)
        print(f"  균등 분배: {1.0/n:.4f} x {n}")

    merged = merge_weights(all_weights, weight_list)
    n_merged_params = sum(v.numel() for v in merged.values())
    print(f"  병합 완료: 키 {len(merged)}, 파라미터 {n_merged_params:,}")

    # 4. 저장
    print("\n" + "=" * 60)
    print("Step 4: 병합 어댑터 저장")
    print("=" * 60)
    os.makedirs(args.output, exist_ok=True)

    # Changed: safetensors 형식으로 저장.
    # Why: HuggingFace 표준 — 로드 속도 빠르고 안전.
    from safetensors.torch import save_file
    output_safetensors = os.path.join(args.output, "adapter_model.safetensors")
    save_file(merged, output_safetensors)
    print(f"  가중치 저장: {output_safetensors}")

    # Changed: adapter_config.json 복사 (첫 번째 어댑터 기준).
    # Why: 동일 아키텍처이므로 어느 것을 복사해도 동일.
    src_config = os.path.join(args.adapters[0], "adapter_config.json")
    dst_config = os.path.join(args.output, "adapter_config.json")
    shutil.copy2(src_config, dst_config)
    print(f"  설정 복사: {dst_config}")

    # Changed: tokenizer 파일도 복사 (있으면).
    # Why: LoRASolver가 adapter_path에서 tokenizer를 로드함.
    tokenizer_files = [
        "tokenizer_config.json", "tokenizer.json", "special_tokens_map.json",
        "vocab.json", "merges.txt",
    ]
    copied_tokenizer = False
    for tf in tokenizer_files:
        src_tf = os.path.join(args.adapters[0], tf)
        if os.path.exists(src_tf):
            shutil.copy2(src_tf, os.path.join(args.output, tf))
            copied_tokenizer = True
    if copied_tokenizer:
        print(f"  토크나이저 복사 완료")

    # 5. 통계
    if not args.no_stats:
        print_weight_stats(all_weights, merged, adapter_names)

    print("\n" + "=" * 60)
    print("병합 완료!")
    print(f"출력 경로: {args.output}")
    print(f"사용법: --adapter-path {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
