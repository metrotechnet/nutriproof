from typing import List, Dict, Optional
import math

def get_center(block: Dict) -> (float, float):
    """Return the center (x, y) of a block from its bounding box."""
    bbox = block["bounding_box"]
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def find_next_right_block(blocks: List[Dict], selected_block: Dict) -> Optional[Dict]:
    """Find the block closest to the right of the selected one."""
    sel_x, sel_y = get_center(selected_block)

    right_candidates = []
    for block in blocks:
        if block == selected_block:
            continue
        x, y = get_center(block)
        
        # Only consider blocks strictly to the right and roughly aligned vertically
        if x > sel_x and abs(y - sel_y) < 50:  # 50 pixels tolerance
            # Distance metric: horizontal priority, then vertical closeness
            dist = math.hypot(x - sel_x, y - sel_y)
            right_candidates.append((dist, block))

    if not right_candidates:
        return None
    
    # Return block with minimum distance
    return min(right_candidates, key=lambda b: b[0])[1]



# Read data from uploads/main/e2e67b48/output_page_1.json
import json

with open("uploads/main/5e2294ae/output_page_1.json", "r") as f:
    data = json.load(f)

blocks = data

# Find block that has text equal to Glucose. case insensitive
selected = next((b for b in blocks if b["text"].strip().lower() == "glucose"), None)

if selected:
    print("Selected block:", selected["text"])
    next_block = find_next_right_block(blocks, selected)

if next_block:
    print("Next right block:", next_block["text"])
else:
    print("No block found to the right.")
