import logging
import pathlib
from typing import Tuple

import numpy as np
from PIL import Image


def _load_band(path: pathlib.Path, resize: Tuple[int, int]) -> np.ndarray:
    img = Image.open(path).convert("L").resize(resize)
    return np.asarray(img, dtype=np.float32)


def load_rgb_and_nir(
    rgb_path: pathlib.Path, nir_path: pathlib.Path, resize: Tuple[int, int]
) -> Tuple[np.ndarray, np.ndarray]:
    """Load the RGB and NIR images. Raises FileNotFoundError if missing."""
    logging.info("Loading RGB from %s", rgb_path)
    logging.info("Loading NIR from %s", nir_path)
    rgb = Image.open(rgb_path).convert("RGB").resize(resize)
    rgb_np = np.asarray(rgb, dtype=np.float32)
    nir_np = _load_band(nir_path, resize)
    return rgb_np, nir_np
