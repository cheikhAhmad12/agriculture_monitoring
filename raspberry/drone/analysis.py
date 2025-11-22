import logging
import pathlib
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from . import camera


@dataclass
class NDVIResult:
    ndvi_map: np.ndarray
    mean: float
    minimum: float
    maximum: float
    stress_ratio: float  # percentage of pixels below threshold


def compute_ndvi(rgb: np.ndarray, nir: np.ndarray, epsilon: float = 1e-6) -> np.ndarray:
    """NDVI = (NIR - Red) / (NIR + Red)."""
    red_channel = rgb[:, :, 0].astype(np.float32)
    denom = (nir + red_channel + epsilon)
    ndvi = (nir - red_channel) / denom
    ndvi = np.clip(ndvi, -1.0, 1.0)
    return ndvi


def summarize_ndvi(ndvi: np.ndarray, stress_threshold: float) -> NDVIResult:
    total_pixels = ndvi.size
    stressed = float(np.sum(ndvi < stress_threshold))
    stress_ratio = (stressed / total_pixels) if total_pixels else 0.0
    return NDVIResult(
        ndvi_map=ndvi,
        mean=float(np.mean(ndvi)),
        minimum=float(np.min(ndvi)),
        maximum=float(np.max(ndvi)),
        stress_ratio=stress_ratio,
    )


def run_ndvi_pipeline(
    rgb_path: pathlib.Path,
    nir_path: pathlib.Path,
    resize: Tuple[int, int],
    stress_threshold: float,
) -> Dict:
    rgb_np, nir_np = camera.load_rgb_and_nir(rgb_path, nir_path, resize)
    ndvi_map = compute_ndvi(rgb_np, nir_np)
    summary = summarize_ndvi(ndvi_map, stress_threshold)
    logging.info(
        "NDVI summary mean=%.3f min=%.3f max=%.3f stress=%.1f%%",
        summary.mean,
        summary.minimum,
        summary.maximum,
        summary.stress_ratio * 100,
    )
    return {
        "mean": summary.mean,
        "min": summary.minimum,
        "max": summary.maximum,
        "stress_ratio": summary.stress_ratio,
    }
