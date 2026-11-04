"""Portable JSON forest inference. Never deserialize pickle/joblib or execute model code."""

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kubesentinel_ml import FEATURE_VERSION
from kubesentinel_ml.features import FEATURES, Window
from kubesentinel_ml.rules import Explanation, Score, rule_score


def path_adjustment(samples: int) -> float:
    if samples <= 1:
        return 0.0
    if samples == 2:
        return 1.0
    return 2 * (math.log(samples - 1) + 0.5772156649015329) - 2 * (samples - 1) / samples


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    feature: int = Field(ge=-2, lt=len(FEATURES))
    threshold: float
    left: int
    right: int
    samples: int = Field(ge=1, le=4096)


class Tree(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[Node] = Field(min_length=1, max_length=8191)

    @model_validator(mode="after")
    def validate_tree(self) -> "Tree":
        visited: set[int] = set()

        def visit(index: int, depth: int) -> None:
            if index < 0 or index >= len(self.nodes) or index in visited or depth > 32:
                raise ValueError("Invalid tree topology")
            visited.add(index)
            node = self.nodes[index]
            if node.feature >= 0:
                visit(node.left, depth + 1)
                visit(node.right, depth + 1)
            elif node.left != -1 or node.right != -1:
                raise ValueError("Invalid leaf")

        visit(0, 0)
        if len(visited) != len(self.nodes):
            raise ValueError("Unreachable tree nodes")
        return self


class Bundle(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    format_version: str = "1"
    feature_version: str = FEATURE_VERSION
    feature_order: list[str]
    window_seconds: int = Field(ge=10, le=3600)
    model_version: str = ""
    center: list[float]
    scale: list[float]
    forest: list[Tree] = Field(min_length=1, max_length=256)
    max_samples: int = Field(ge=2, le=4096)
    statistical_threshold: float = Field(gt=0)
    forest_threshold: float = Field(gt=0, le=2)
    metadata: dict[str, Any]

    @model_validator(mode="after")
    def contract(self) -> "Bundle":
        if self.format_version != "1" or self.feature_version != FEATURE_VERSION:
            raise ValueError("Unsupported model/feature version")
        if self.feature_order != list(FEATURES):
            raise ValueError("Incompatible feature order")
        if len(self.center) != len(FEATURES) or len(self.scale) != len(FEATURES):
            raise ValueError("Invalid normalization dimensions")
        if any(value <= 0 for value in self.scale):
            raise ValueError("Invalid scale")
        return self

    def digest(self) -> str:
        body = self.model_dump(exclude={"model_version"})
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()

    def save(self, path: Path) -> None:
        self.model_version = self.digest()
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Bundle":
        if path.stat().st_size > 16_000_000:
            raise ValueError("Oversized model artifact")
        bundle = cls.model_validate_json(path.read_bytes())
        if bundle.model_version != bundle.digest():
            raise ValueError("Model checksum mismatch")
        return bundle

    def vector(self, window: Window) -> list[float]:
        result = []
        for i, key in enumerate(FEATURES):
            value = window.values[key]
            result.append(self.center[i] if value is None else value)
        return result

    def raw_scores(self, window: Window) -> tuple[float, float, list[Explanation]]:
        vector = self.vector(window)
        deviations = [
            (abs(v - self.center[i]) / self.scale[i], i)
            for i, v in enumerate(vector)
            if window.values[FEATURES[i]] is not None
        ]
        deviations.sort(reverse=True)
        evidence = [
            Explanation(
                feature=FEATURES[i],
                value=vector[i],
                reference=self.center[i],
                detail=f"Robust deviation {z:.3f} scale units; context, not causal attribution",
            )
            for z, i in deviations[:5]
        ]
        depth_sum = 0.0
        for tree in self.forest:
            index, depth = 0, 0
            while tree.nodes[index].feature >= 0:
                node = tree.nodes[index]
                # sklearn IsolationForest converts input to float32 before tree traversal.
                import struct

                value = struct.unpack("f", struct.pack("f", vector[node.feature]))[0]
                index = node.left if value <= node.threshold else node.right
                depth += 1
            depth_sum += depth + path_adjustment(tree.nodes[index].samples)
        forest_score = 2 ** (-depth_sum / (len(self.forest) * path_adjustment(self.max_samples)))
        return max((z for z, _ in deviations), default=0.0), forest_score, evidence

    def score(self, window: Window, detector: str = "isolation_forest") -> Score:
        if window.feature_version != self.feature_version:
            raise ValueError("Feature version mismatch")
        if window.coverage < 0.75:
            return rule_score(window)
        statistical, forest, evidence = self.raw_scores(window)
        value = statistical if detector == "robust_statistics" else forest
        threshold = (
            self.statistical_threshold if detector == "robust_statistics" else self.forest_threshold
        )
        anomalous = value >= threshold
        drift = ["extreme_feature_shift"] if statistical > 12 else []
        if window.clipped:
            drift.append("physical_cap_exceeded")
        return Score(
            detector=detector,
            score=value,
            threshold=threshold,
            anomalous=anomalous,
            severity="warning" if anomalous else "info",
            explanations=evidence,
            quality="ok",
            model_version=self.model_version,
            drift=drift,
        )
