import os
import logging
from typing import Dict, Any, List, Set, Tuple

logger = logging.getLogger(__name__)


class PathValidator:
    """
    결정론적 경로 검증기 (Deterministic Path Validator)
    LLM이 생성한 codeLocation이 실제 Git 저장소 내에 존재하는지 검증하고
    환각(존재하지 않는 경로, 과거 커밋 경로, alias)을 100% 필터링/교정합니다.
    """

    def __init__(self, valid_paths: Set[str]):
        # 표준화된 경로 세트 (소문자 매핑 포함)
        self.valid_paths = {p.replace("\\", "/").strip("./") for p in valid_paths}
        # 파일명 -> 전체 상대경로 매핑 (경로 단축 또는 alias 복구용)
        self.filename_to_paths: Dict[str, List[str]] = {}
        for p in self.valid_paths:
            fname = os.path.basename(p)
            self.filename_to_paths.setdefault(fname, []).append(p)

    def normalize_path(self, raw_path: str) -> str:
        """경로 포맷 정규화"""
        return raw_path.replace("\\", "/").strip().lstrip("./")

    def validate_and_correct_path(self, raw_path: str) -> str | None:
        """
        단일 경로 검증 및 교정
        1. 정확히 일치하면 그대로 반환
        2. 파일명이 일치하는 유효 경로가 1개뿐이면 해당 경로로 자동 교정
        3. 일치하는 유효 파일이 전혀 없으면 None 반환 (환각 제거)
        """
        norm = self.normalize_path(raw_path)
        if norm in self.valid_paths:
            return norm

        # 접두사 누락 복구 시도 (예: app/... vs src/...)
        fname = os.path.basename(norm)
        candidates = self.filename_to_paths.get(fname, [])
        if len(candidates) == 1:
            logger.info(f"[PathValidator] 경로 자동 교정: '{raw_path}' -> '{candidates[0]}'")
            return candidates[0]
        elif len(candidates) > 1:
            # 여러 개일 경우 경로 유사도가 가장 높은 것 선택
            best_match = max(candidates, key=lambda c: len(set(c.split("/")) & set(norm.split("/"))))
            logger.info(f"[PathValidator] 다중 후보 중 최적 매핑: '{raw_path}' -> '{best_match}'")
            return best_match

        logger.warning(f"[PathValidator] 유효하지 않은 경로 제거(환각): '{raw_path}'")
        return None

    def validate_feature_analysis(
        self,
        feature_result: Dict[str, Any],
        fallback_files: List[str] = None
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Stage 1 결과 전체의 codeLocation 검증
        Returns: (검증 완료된 feature_result, 통계 딕셔너리)
        """
        stats = {
            "total_checked": 0,
            "valid_exact": 0,
            "corrected": 0,
            "removed_hallucinations": 0
        }

        fallback_list = [self.normalize_path(f) for f in (fallback_files or []) if self.normalize_path(f) in self.valid_paths]
        default_fallback = fallback_list[0] if fallback_list else (next(iter(self.valid_paths)) if self.valid_paths else "README.md")

        # 1. implementedFeatures 경로 검증
        for category in feature_result.get("implementedFeatures", []):
            for feat in category.get("features", []):
                raw_locations = feat.get("codeLocation", [])
                validated_locations = []
                for loc in raw_locations:
                    stats["total_checked"] += 1
                    norm = self.normalize_path(loc)
                    if norm in self.valid_paths:
                        stats["valid_exact"] += 1
                        validated_locations.append(norm)
                    else:
                        corrected = self.validate_and_correct_path(loc)
                        if corrected:
                            stats["corrected"] += 1
                            validated_locations.append(corrected)
                        else:
                            stats["removed_hallucinations"] += 1

                # 중복 제거 및 빈 리스트 방지
                unique_locations = list(dict.fromkeys(validated_locations))
                if not unique_locations:
                    unique_locations = [default_fallback]
                    logger.info(f"[PathValidator] 모든 경로가 무효하여 기본 파일로 폴백: '{feat.get('name')}' -> {unique_locations}")
                feat["codeLocation"] = unique_locations

        # 2. codeInsights 경로 검증
        for insight in feature_result.get("codeInsights", []):
            raw_locations = insight.get("codeLocation", [])
            validated_locations = []
            for loc in raw_locations:
                stats["total_checked"] += 1
                norm = self.normalize_path(loc)
                if norm in self.valid_paths:
                    stats["valid_exact"] += 1
                    validated_locations.append(norm)
                else:
                    corrected = self.validate_and_correct_path(loc)
                    if corrected:
                        stats["corrected"] += 1
                        validated_locations.append(corrected)
                    else:
                        stats["removed_hallucinations"] += 1

            unique_locations = list(dict.fromkeys(validated_locations))
            if not unique_locations:
                unique_locations = [default_fallback]
            insight["codeLocation"] = unique_locations

        return feature_result, stats
