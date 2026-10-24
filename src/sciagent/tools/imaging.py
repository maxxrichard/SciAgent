"""Imaging tools: nucleus segmentation and per-image feature extraction."""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from sciagent.data import synthetic
from sciagent.tools.registry import Tool


def otsu_threshold(img: np.ndarray, bins: int = 256) -> float:
    hist, edges = np.histogram(img.ravel(), bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m = np.cumsum(hist * centers)
    mu0 = np.divide(m, w0, out=np.zeros_like(m, dtype=float), where=w0 > 0)
    mu1 = np.divide(m[-1] - m, w1, out=np.zeros_like(m, dtype=float), where=w1 > 0)
    between = w0 * w1 * (mu0 - mu1) ** 2
    return float(centers[int(np.argmax(between))])


def label_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-connected component labelling via breadth-first search."""
    labels = np.zeros(mask.shape, dtype=np.int32)
    h, w = mask.shape
    current = 0
    for y, x in zip(*np.nonzero(mask), strict=True):
        if labels[y, x]:
            continue
        current += 1
        labels[y, x] = current
        queue = deque([(y, x)])
        while queue:
            cy, cx = queue.popleft()
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = current
                    queue.append((ny, nx))
    return labels, current


class SegmentCellsInput(BaseModel):
    sample_id: str = Field(..., pattern=r"^IMG-\d{4}$", description="Image identifier, IMG-0001")
    threshold: float | None = Field(None, ge=0, le=1, description="Override Otsu threshold")
    min_area: int = Field(5, ge=1, le=500, description="Discard objects smaller than this")


def segment_cells(p: SegmentCellsInput) -> dict[str, Any]:
    img = synthetic.microscopy_image(p.sample_id)
    thr = p.threshold if p.threshold is not None else otsu_threshold(img)
    labels, n = label_components(img > thr)
    areas = np.bincount(labels.ravel())[1:]
    kept = areas[areas >= p.min_area]
    return {
        "sample_id": p.sample_id,
        "threshold": round(thr, 4),
        "cell_count": int(kept.size),
        "discarded_objects": int(n - kept.size),
        "mean_area_px": round(float(kept.mean()), 2) if kept.size else 0.0,
        "median_area_px": float(np.median(kept)) if kept.size else 0.0,
    }


class ImageFeaturesInput(BaseModel):
    sample_id: str = Field(..., pattern=r"^IMG-\d{4}$")


def extract_image_features(p: ImageFeaturesInput) -> dict[str, Any]:
    img = synthetic.microscopy_image(p.sample_id)
    gy, gx = np.gradient(img)
    thr = otsu_threshold(img)
    return {
        "sample_id": p.sample_id,
        "mean_intensity": round(float(img.mean()), 4),
        "std_intensity": round(float(img.std()), 4),
        "foreground_fraction": round(float((img > thr).mean()), 4),
        "gradient_energy": round(float(np.mean(gx**2 + gy**2)), 5),
        "snr_db": round(float(10 * np.log10(img[img > thr].mean() / img[img <= thr].std())), 2),
    }


TOOLS = [
    Tool(
        "segment_cells",
        "Segment nuclei in a microscopy image and report cell count and size statistics.",
        "imaging",
        SegmentCellsInput,
        segment_cells,
    ),
    Tool(
        "extract_image_features",
        "Compute intensity, texture and signal-to-noise features for a microscopy image.",
        "imaging",
        ImageFeaturesInput,
        extract_image_features,
    ),
]
