import math
import os
from typing import Dict, List, Tuple

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - graceful fallback when OpenCV is missing
    cv2 = None


Bbox = List[List[int]]


class GridDetector:
    """Detects table/grid cells and checks if each cell contains a mark."""

    def __init__(self, cluster_tolerance: int = 10):
        self.cluster_tolerance = cluster_tolerance

    def detect_grid_cells(self, image_path: str) -> Dict:
        if cv2 is None:
            return {
                "error": "OpenCV is not available. Please install opencv-python-headless.",
                "rows": [],
                "cols": [],
                "cells": [],
                "checked_cells": [],
            }

        gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            return {
                "error": f"Unable to read image: {image_path}",
                "rows": [],
                "cols": [],
                "cells": [],
                "checked_cells": [],
            }

        # Adaptive threshold helps with uneven illumination in scanned forms.
        binary_inv = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            35,
            12,
        )
        os.makedirs("debug", exist_ok=True)

        # Save binary image for debugging
        binary_inv_color = cv2.cvtColor(binary_inv, cv2.COLOR_GRAY2BGR)
        cv2.imwrite("debug/binary_inv.png", binary_inv_color)

        h, w = binary_inv.shape
        # Contour-component approach for irregular grids made of isolated boxes.
        pre = cv2.morphologyEx(
            binary_inv,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
            iterations=1,
        )

        contours, _ = cv2.findContours(pre, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        image_area = float(h * w)
        min_bbox_area = max(40.0, image_area // 600 )
        max_bbox_area = image_area * 0.35

        candidates = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw < 8 or bh < 8:
                continue

            bbox_area = float(bw * bh)
            if bbox_area < min_bbox_area or bbox_area > max_bbox_area:
                continue

            aspect_ratio = bw / float(bh)
            if aspect_ratio < 0.15 or aspect_ratio > 12.0:
                continue

            # Discard likely full-page rule lines.
            if bw > int(0.65 * w) and bh < max(8, h // 100):
                continue
            if bh > int(0.65 * h) and bw < max(8, w // 100):
                continue

            candidates.append((x, y, bw, bh))

        # Remove near-duplicate nested boxes.
        deduped: List[Tuple[int, int, int, int]] = []
        for box in sorted(candidates, key=lambda b: b[2] * b[3], reverse=True):
            if any(self._bbox_iou(box, kept) > 0.82 for kept in deduped):
                continue
            deduped.append(box)

        if len(deduped) < 2:
            return {
                "error": "Could not infer grid components from contours.",
                "rows": [],
                "cols": [],
                "cells": [],
                "checked_cells": [],
            }

        median_h = int(np.median([b[3] for b in deduped]))
        median_w = int(np.median([b[2] for b in deduped]))
        row_tol = max(self.cluster_tolerance, int(median_h * 0.6))
        col_tol = max(self.cluster_tolerance, int(median_w * 0.6))

        row_centers = [y + bh // 2 for (_, y, _, bh) in deduped]
        col_centers = [x + bw // 2 for (x, _, bw, _) in deduped]
        rows = self._cluster_coordinates(row_centers, row_tol)
        cols = self._cluster_coordinates(col_centers, col_tol)

        # One distinct color per row cluster for debug visualization.
        row_colors = [
            (60, 180, 75), (230, 25, 75), (0, 130, 200), (245, 130, 48),
            (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60),
            (250, 190, 212), (0, 128, 128), (220, 190, 255), (170, 110, 40),
        ]

        rng = np.random.default_rng(42)

        cells = []
        cell_fill_colors: List[Tuple[int, int, int]] = []
        # Two-pass rendering: fill pass first, then borders/labels on top.
        fill_layer = binary_inv_color.copy()
        overlay = binary_inv_color.copy()

        for (x, y, bw, bh) in sorted(deduped, key=lambda b: (b[1], b[0])):
            x1, y1 = x, y
            x2, y2 = x + bw, y + bh

            row_idx = self._nearest_cluster_index(y + bh // 2, rows)
            col_idx = self._nearest_cluster_index(x + bw // 2, cols)
            if row_idx < 0 or col_idx < 0:
                continue

            bbox = self._to_bbox(x1, y1, x2, y2)
            cell_info = {
                "row": row_idx,
                "col": col_idx,
                "bbox": bbox,
            }
            cells.append(cell_info)

            # Random fill color per cell, distinct row color for outline.
            fill_color = tuple(int(v) for v in rng.integers(80, 230, size=3))
            cell_fill_colors.append(fill_color)
            cv2.rectangle(fill_layer, (x1, y1), (x2, y2), fill_color, cv2.FILLED)

        # Blend fill layer at 30 % opacity into the overlay.
        overlay = cv2.addWeighted(fill_layer, 0.30, overlay, 0.70, 0)

        # Draw borders and labels on top of the blended image.
        for cell, fill_color in zip(cells, cell_fill_colors):
            (x1, y1), _, (x2, y2), _ = cell["bbox"]
            row_idx = cell["row"]
            outline_color = row_colors[row_idx % len(row_colors)]
            cv2.rectangle(overlay, (x1, y1), (x2, y2), outline_color, 2)
            cv2.putText(
                overlay,
                f"r{row_idx}c{cell['col']}",
                (x1 + 3, y1 + 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                outline_color,
                1,
                cv2.LINE_AA,
            )

        cv2.imwrite("debug/cells_detected.png", overlay)

        return {
            "rows": rows,
            "cols": cols,
            "cells": cells,
            "checked_cells": [],
        }

    @staticmethod
    def _extract_intersection_points(intersection_img: np.ndarray) -> List[Tuple[int, int]]:
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(intersection_img, connectivity=8)
        points: List[Tuple[int, int]] = []
        for i in range(1, num_labels):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < 3:
                continue
            cx, cy = centroids[i]
            points.append((int(round(cx)), int(round(cy))))
        return points

    @staticmethod
    def _cluster_coordinates(values: List[int], tolerance: int) -> List[int]:
        if not values:
            return []

        sorted_vals = sorted(values)
        clusters: List[List[int]] = [[sorted_vals[0]]]

        for value in sorted_vals[1:]:
            if abs(value - clusters[-1][-1]) <= tolerance:
                clusters[-1].append(value)
            else:
                clusters.append([value])

        # Keep cluster centers only.
        return [int(round(sum(cluster) / len(cluster))) for cluster in clusters]

    @staticmethod
    def _to_bbox(x1: int, y1: int, x2: int, y2: int) -> Bbox:
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    @staticmethod
    def _nearest_cluster_index(value: int, clusters: List[int]) -> int:
        if not clusters:
            return -1
        return min(range(len(clusters)), key=lambda i: abs(clusters[i] - value))

    @staticmethod
    def _bbox_iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
        ax1, ay1, aw, ah = a
        bx1, by1, bw, bh = b
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = float(iw * ih)
        if inter <= 0:
            return 0.0

        union = float(aw * ah + bw * bh) - inter
        if union <= 0:
            return 0.0
        return inter / union


