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

    @staticmethod
    def _candidate_parts(candidate):
        """Normalize candidate shape to (x, y, bw, bh, contour_or_none)."""
        if len(candidate) >= 5:
            return candidate[0], candidate[1], candidate[2], candidate[3], candidate[4]
        return candidate[0], candidate[1], candidate[2], candidate[3], None

    def _save_debug_contours(self, base_img, candidates, filename, color=(0, 255, 0), thickness=2):
        """Save remaining contours/boxes for a detection stage."""
        if cv2 is None:
            return
        debug_img = base_img.copy()
        for cand in candidates:
            x, y, bw, bh, cnt = self._candidate_parts(cand)
            if cnt is not None:
                cv2.drawContours(debug_img, [cnt], -1, color, thickness)
            else:
                cv2.rectangle(debug_img, (x, y), (x + bw, y + bh), color, thickness)
        cv2.imwrite(os.path.join("debug", filename), debug_img)

    def detect_grid_cells(self, image) -> Dict:
        if cv2 is None:
            return {
                "error": "OpenCV is not available. Please install opencv-python-headless.",
                "rows": [],
                "cols": [],
                "cells": [],
                "all_detected_cells": [],
                "checked_cells": [],
            }

        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        if gray is None:
            return {
                "error": f"Unable to process image.",
                "rows": [],
                "cols": [],
                "cells": [],
                "all_detected_cells": [],
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

 
        h, w = binary_inv.shape
        # Contour-component approach for irregular grids made of isolated boxes.
        pre = cv2.morphologyEx(
            binary_inv,
            cv2.MORPH_DILATE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
            iterations=3,
        )

        # Save binary image for debugging
        binary_inv_color = cv2.cvtColor(pre, cv2.COLOR_GRAY2BGR)
        cv2.imwrite("debug/binary_inv.png", binary_inv_color)

        contours, _ = cv2.findContours(pre, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        # Filter contour by shape analysis (rectangle-like only).
        
        # First pass: minimal hard filters only (absolute pixel size, aspect, lines).
        candidates = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw < 40 or bw> 0.3*w or bh < 40 or bh > 500:
                continue

            contour_area = cv2.contourArea(cnt)
            rect_area = float(bw * bh)
            if contour_area <= 0 or rect_area <= 0:
                continue
            # Rectangle fill ratio (extent): reject very hollow/irregular shapes.
            extent = contour_area / rect_area
            if extent < 0.8:
                continue

            candidates.append((x, y, bw, bh, cnt))

        # self._save_debug_contours(binary_inv_color, candidates, "contours_step1_candidates.png", color=(255, 0, 0), thickness=2)

        all_detected_cells = [
            {
                "bbox": self._to_bbox(x, y, x + bw, y + bh),
                "source": "raw_contour",
            }
            for (x, y, bw, bh, _) in candidates
        ]

 
        # Remove near-duplicate nested boxes.
        deduped = []
        for box in sorted(candidates, key=lambda b: self._candidate_parts(b)[2] * self._candidate_parts(b)[3], reverse=True):
            bx = self._candidate_parts(box)
            if any(
                   self._bbox_iou((bx[0], bx[1], bx[2], bx[3]), (kx[0], kx[1], kx[2], kx[3])) > 0.82
                   or self._bbox_contained((bx[0], bx[1], bx[2], bx[3]), (kx[0], kx[1], kx[2], kx[3]), min_ratio=0.9)
                   for kx in (self._candidate_parts(kept) for kept in deduped)):
                continue
            deduped.append(box)

        # self._save_debug_contours(binary_inv_color, deduped, "contours_step2_deduped.png", color=(0, 255, 0), thickness=2)


        if len(deduped) < 2:
            return {
                "error": "Could not infer grid components from contours.",
                "rows": [],
                "cols": [],
                "cells": [],
                "all_detected_cells": all_detected_cells,
                "checked_cells": [],
            }

        median_h = int(np.median([self._candidate_parts(b)[3] for b in deduped]))
        median_w = int(np.median([self._candidate_parts(b)[2] for b in deduped]))
        row_tol = max(self.cluster_tolerance, int(median_h * 0.15))
        col_tol = max(self.cluster_tolerance, int(median_w * 0.6))

        row_centers = [self._candidate_parts(b)[1] + self._candidate_parts(b)[3] // 2 for b in deduped]
        col_centers = [self._candidate_parts(b)[0] + self._candidate_parts(b)[2] // 2 for b in deduped]
        rows = self._cluster_coordinates(row_centers, row_tol)
        cols = self._cluster_coordinates(col_centers, col_tol)



        cells = []
        cell_boxes: List[Tuple[int, int, int, int]] = []
        # Two-pass rendering: fill pass first, then borders/labels on top.
        for box in sorted(deduped, key=lambda b: (self._candidate_parts(b)[1], self._candidate_parts(b)[0])):
            x, y, bw, bh, _ = self._candidate_parts(box)
            x1, y1 = x, y
            x2, y2 = x + bw, y + bh

            row_idx = self._nearest_cluster_index(y + bh // 2, rows)
            col_idx = self._nearest_cluster_index(x + bw // 2, cols)
            if row_idx < 0 or col_idx < 0:
                continue

            bbox = self._to_bbox(x1, y1, x2, y2)
            cells.append({
                "row": row_idx,
                "col": col_idx,
                "bbox": bbox,
            })
            cell_boxes.append((x1, y1, x2, y2))

     

        # final_stage = [(x1, y1, x2 - x1, y2 - y1) for (x1, y1, x2, y2) in cell_boxes]
        # self._save_debug_contours(binary_inv_color, final_stage, "contours_step3_final_cells.png", color=(0, 0, 255), thickness=2)

        # Re-index row/col after filtering so indices are contiguous and
        # the returned rows/cols arrays only contain clusters still in use.
        used_rows = sorted({c["row"] for c in cells})
        row_remap = {old: new for new, old in enumerate(used_rows)}
        for c in cells:
            c["row"] = row_remap[c["row"]]
        rows = [rows[i] for i in used_rows]

        # Per-row column reindexing: within each row, sort cells left-to-right
        # by their bbox x position and assign col = 0, 1, 2, ... so every row
        # starts its column numbering at 0 (independent of other rows).
        from collections import defaultdict
        cells_by_row = defaultdict(list)
        for c in cells:
            cells_by_row[c["row"]].append(c)
        for row_cells in cells_by_row.values():
            row_cells.sort(key=lambda c: c["bbox"][0][0])
            for new_col, c in enumerate(row_cells):
                c["col"] = new_col

        # Rebuild a flat cols array as the union of column x-centers across rows
        # so callers still have a reference list. Use bbox centers for accuracy.
        max_cols = max((len(rc) for rc in cells_by_row.values()), default=0)
        cols = []
        for ci in range(max_cols):
            xs = [
                (rc[ci]["bbox"][0][0] + rc[ci]["bbox"][2][0]) // 2
                for rc in cells_by_row.values()
                if ci < len(rc)
            ]
            cols.append(int(round(sum(xs) / len(xs))) if xs else 0)

        return {
            "rows": rows,
            "cols": cols,
            "cells": cells,
            "all_detected_cells": all_detected_cells,
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

    @staticmethod
    def _bbox_contained(inner: Tuple[int, int, int, int], outer: Tuple[int, int, int, int], min_ratio: float = 0.9) -> bool:
        """True if `inner` lies mostly inside `outer` by area overlap ratio."""
        ix1, iy1, iw, ih = inner
        ox1, oy1, ow, oh = outer
        ix2, iy2 = ix1 + iw, iy1 + ih
        ox2, oy2 = ox1 + ow, oy1 + oh

        inter_x1 = max(ix1, ox1)
        inter_y1 = max(iy1, oy1)
        inter_x2 = min(ix2, ox2)
        inter_y2 = min(iy2, oy2)
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter = float(inter_w * inter_h)

        inner_area = float(max(1, iw * ih))
        return (inter / inner_area) >= min_ratio


