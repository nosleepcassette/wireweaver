"""
router.py — Orthogonal Wire Routing Engine
===========================================
Routes wires between component pins using clean, non-overlapping
orthogonal (right-angle) paths. Uses a grid-based approach with
an A*-like pathfinder to avoid collisions.

Wire routing is the hardest part of electronic diagram generation.
This implementation uses a simplified channel router suitable for
diagrams with <50 connections.
"""

import svgwrite
from typing import List, Tuple, Dict, Set, Optional
from dataclasses import dataclass, field
import heapq
import math


# ─── Wire color scheme ───────────────────────────────────────────
# Color-coded by function for instant visual parsing
WIRE_COLORS = {
    "power":    "#cc2222",   # red for VCC/5V/3.3V
    "ground":   "#222222",   # black for GND
    "data":     "#2255cc",   # blue for data lines (DIN, MOSI)
    "clock":    "#22aa44",   # green for clock (CLK, SCK)
    "cs":       "#ccaa22",   # yellow for chip select
    "analog":   "#8833cc",   # purple for analog signals
    "digital":  "#cc6622",   # orange for generic digital
    "signal":   "#cc22aa",   # pink for misc signals
}

# Map pin names to wire categories for auto-coloring
PIN_COLOR_MAP = {
    "5V": "power", "3.3V": "power", "VCC": "power", "VIN": "power",
    "+": "power",
    "GND": "ground", "GND.1": "ground", "GND.2": "ground",
    "GND.3": "ground", "-": "ground",
    "DIN": "data", "MOSI": "data", "MISO": "data", "SDA": "data",
    "CLK": "clock", "SCK": "clock", "SCL": "clock",
    "CS": "cs", "SS": "cs", "LOAD": "cs",
    "A0": "analog", "A1": "analog", "A2": "analog",
    "A3": "analog", "A4": "analog", "A5": "analog",
}


@dataclass
class Wire:
    """Represents a connection between two component pins."""
    from_comp: str         # component id
    from_pin: str          # pin name on source component
    to_comp: str           # component id
    to_pin: str            # pin name on target component
    color: Optional[str] = None   # override color (hex)
    label: Optional[str] = None   # optional wire label
    category: str = "digital"     # auto-detected category


@dataclass(order=True)
class PQEntry:
    """Priority queue entry for A* pathfinding."""
    priority: float
    pos: Tuple[int, int] = field(compare=False)
    path: List[Tuple[int, int]] = field(compare=False)


class WireRouter:
    """
    Grid-based orthogonal wire router.

    The canvas is divided into a coarse grid (default 5px cells).
    Each wire is routed using A* on this grid, with already-routed
    wire segments marked as occupied to prevent overlaps.

    The router processes wires in order of shortest Manhattan distance
    first, giving short direct connections priority over long runs
    that have more routing flexibility.
    """

    GRID_SIZE = 4          # pixels per grid cell (finer = smoother routes)
    WIRE_WIDTH = 2.2       # SVG stroke width for wires
    DOT_RADIUS = 3.5       # termination dot radius
    BEND_PENALTY = 3       # cost multiplier for direction changes
    NEAR_WIRE_PENALTY = 8  # cost for routing adjacent to existing wire

    def __init__(self, canvas_w: int, canvas_h: int):
        self.grid_w = canvas_w // self.GRID_SIZE + 1
        self.grid_h = canvas_h // self.GRID_SIZE + 1
        # Track occupied grid cells: set of (gx, gy) tuples
        self.occupied: Set[Tuple[int, int]] = set()
        # Track cells adjacent to wires (for spacing penalty)
        self.near_wire: Set[Tuple[int, int]] = set()
        # Component bounding boxes to avoid routing through
        self.blocked_zones: List[Tuple[int, int, int, int]] = []  # (gx1, gy1, gx2, gy2)

    def _to_grid(self, x: float, y: float) -> Tuple[int, int]:
        """Convert canvas coordinates to grid coordinates."""
        return (round(x / self.GRID_SIZE), round(y / self.GRID_SIZE))

    def _to_canvas(self, gx: int, gy: int) -> Tuple[float, float]:
        """Convert grid coordinates back to canvas coordinates."""
        return (gx * self.GRID_SIZE, gy * self.GRID_SIZE)

    def add_blocked_zone(self, x1: float, y1: float, x2: float, y2: float,
                         margin: int = 2):
        """
        Mark a rectangular area as blocked (component body).
        Wires cannot route through blocked zones.
        margin: extra grid cells of padding around the zone.
        """
        gx1, gy1 = self._to_grid(x1 - margin * self.GRID_SIZE,
                                   y1 - margin * self.GRID_SIZE)
        gx2, gy2 = self._to_grid(x2 + margin * self.GRID_SIZE,
                                   y2 + margin * self.GRID_SIZE)
        self.blocked_zones.append((gx1, gy1, gx2, gy2))

    def _is_blocked(self, gx: int, gy: int) -> bool:
        """Check if a grid cell is inside a blocked zone."""
        for bx1, by1, bx2, by2 in self.blocked_zones:
            if bx1 <= gx <= bx2 and by1 <= gy <= by2:
                return True
        return False

    def _cell_cost(self, gx: int, gy: int, prev_dir: Optional[str],
                    new_dir: str) -> float:
        """
        Calculate the traversal cost for a grid cell.
        Higher cost for: direction changes (bends), near existing wires,
        and cells at canvas edges.
        """
        cost = 1.0

        # Penalize direction changes to encourage straight runs
        if prev_dir is not None and prev_dir != new_dir:
            cost += self.BEND_PENALTY

        # Penalize routing near existing wires (spacing)
        if (gx, gy) in self.near_wire:
            cost += self.NEAR_WIRE_PENALTY

        # Slight penalty near edges
        if gx < 3 or gy < 3 or gx > self.grid_w - 3 or gy > self.grid_h - 3:
            cost += 1.0

        return cost

    def route_wire(self, start: Tuple[float, float],
                    end: Tuple[float, float]) -> List[Tuple[float, float]]:
        """
        Route a single wire from start to end using A* pathfinding
        on the grid. Returns a list of (x, y) waypoints in canvas coords.

        The path is orthogonal (only horizontal and vertical segments)
        and avoids occupied cells and blocked zones.
        """
        sg = self._to_grid(*start)
        eg = self._to_grid(*end)

        # If start/end are very close, just connect directly
        if abs(sg[0] - eg[0]) + abs(sg[1] - eg[1]) <= 2:
            return [start, end]

        # A* pathfinding
        # Directions: right, left, down, up
        directions = [(1, 0, "h"), (-1, 0, "h"), (0, 1, "v"), (0, -1, "v")]

        # Priority queue: (estimated_total_cost, (gx, gy), path_so_far)
        pq = [PQEntry(0, sg, [sg])]
        visited = set()
        g_costs = {sg: 0}

        best_path = None
        max_iterations = 100000  # safety limit (higher for fine grid)

        iterations = 0
        while pq and iterations < max_iterations:
            iterations += 1
            entry = heapq.heappop(pq)
            current = entry.pos
            path = entry.path

            if current == eg:
                best_path = path
                break

            if current in visited:
                continue
            visited.add(current)

            # Determine current direction from last segment
            if len(path) >= 2:
                prev = path[-2]
                if prev[0] != current[0]:
                    prev_dir = "h"
                else:
                    prev_dir = "v"
            else:
                prev_dir = None

            for dx, dy, new_dir in directions:
                nx, ny = current[0] + dx, current[1] + dy

                # Bounds check
                if nx < 0 or ny < 0 or nx >= self.grid_w or ny >= self.grid_h:
                    continue

                # Collision checks
                if (nx, ny) in self.occupied and (nx, ny) != eg:
                    continue
                if self._is_blocked(nx, ny) and (nx, ny) != eg and (nx, ny) != sg:
                    continue
                if (nx, ny) in visited:
                    continue

                # Calculate cost
                step_cost = self._cell_cost(nx, ny, prev_dir, new_dir)
                new_g = g_costs[current] + step_cost

                if (nx, ny) in g_costs and g_costs[(nx, ny)] <= new_g:
                    continue

                g_costs[(nx, ny)] = new_g

                # Heuristic: Manhattan distance to goal
                h = abs(nx - eg[0]) + abs(ny - eg[1])
                f = new_g + h

                new_path = path + [(nx, ny)]
                heapq.heappush(pq, PQEntry(f, (nx, ny), new_path))

        if best_path is None:
            # Fallback: simple L-shaped route (one bend)
            mid_x, mid_y = eg[0], sg[1]
            best_path = [sg, (mid_x, mid_y), eg]

        # Simplify path: collapse consecutive same-direction segments
        simplified = self._simplify_path(best_path)

        # Mark path cells as occupied for future wires
        for gx, gy in best_path:
            self.occupied.add((gx, gy))
            # Mark adjacent cells for spacing penalty
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
                self.near_wire.add((gx + dx, gy + dy))

        # Convert back to canvas coordinates
        # Keep start and end at exact pin positions
        canvas_path = [start]
        for gx, gy in simplified[1:-1]:
            canvas_path.append(self._to_canvas(gx, gy))
        canvas_path.append(end)

        return canvas_path

    def _simplify_path(self, path: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Remove intermediate points on straight segments.
        Only keep waypoints where direction changes (bends).
        """
        if len(path) <= 2:
            return path

        simplified = [path[0]]

        for i in range(1, len(path) - 1):
            prev = path[i - 1]
            curr = path[i]
            next_ = path[i + 1]

            # Check if direction changes at this point
            dx1 = curr[0] - prev[0]
            dy1 = curr[1] - prev[1]
            dx2 = next_[0] - curr[0]
            dy2 = next_[1] - curr[1]

            # Normalize
            dx1 = 0 if dx1 == 0 else dx1 // abs(dx1)
            dy1 = 0 if dy1 == 0 else dy1 // abs(dy1)
            dx2 = 0 if dx2 == 0 else dx2 // abs(dx2)
            dy2 = 0 if dy2 == 0 else dy2 // abs(dy2)

            if (dx1, dy1) != (dx2, dy2):
                simplified.append(curr)

        simplified.append(path[-1])
        return simplified


def detect_wire_category(from_pin: str, to_pin: str) -> str:
    """Auto-detect wire category from pin names for color coding."""
    # Check both pins against the mapping
    for pin in [from_pin, to_pin]:
        # Strip component prefix if present
        pin_clean = pin.split(".")[-1] if "." in pin else pin

        # Check direct match
        if pin_clean in PIN_COLOR_MAP:
            return PIN_COLOR_MAP[pin_clean]

        # Check if it's a power rail reference
        if pin_clean.startswith("tp") or pin_clean.startswith("bp"):
            return "power"
        if pin_clean.startswith("tn") or pin_clean.startswith("bn"):
            return "ground"

    return "digital"  # default


def render_wires(dwg: svgwrite.Drawing,
                 wires: List[Wire],
                 components: Dict[str, 'Component'],
                 router: WireRouter) -> svgwrite.container.Group:
    """
    Route and render all wires, returning an SVG group.

    Wires are processed shortest-first to give direct connections
    priority, with longer wires routed around them.
    """
    g = dwg.g(id="wires")

    # ── Sort wires by Manhattan distance (shortest first) ──
    def wire_distance(w: Wire) -> float:
        try:
            sx, sy = components[w.from_comp].get_pin(w.from_pin)
            ex, ey = components[w.to_comp].get_pin(w.to_pin)
            return abs(ex - sx) + abs(ey - sy)
        except (KeyError, ValueError):
            return float('inf')

    sorted_wires = sorted(wires, key=wire_distance)

    for wire in sorted_wires:
        try:
            start = components[wire.from_comp].get_pin(wire.from_pin)
            end = components[wire.to_comp].get_pin(wire.to_pin)
        except (KeyError, ValueError) as e:
            print(f"WARNING: Could not route wire {wire.from_comp}:{wire.from_pin} -> "
                  f"{wire.to_comp}:{wire.to_pin}: {e}")
            continue

        # Determine color
        if wire.color:
            color = wire.color
        else:
            category = detect_wire_category(wire.from_pin, wire.to_pin)
            wire.category = category
            color = WIRE_COLORS.get(category, WIRE_COLORS["digital"])

        # Route the wire
        path_points = router.route_wire(start, end)

        # ── Render the wire as an SVG polyline ──
        if len(path_points) >= 2:
            # Build the path with rounded corners
            wire_group = dwg.g(class_=f"wire wire-{wire.category}")

            # Shadow/glow effect for depth
            points = [(p[0], p[1]) for p in path_points]
            wire_group.add(dwg.polyline(
                points=points,
                stroke=color, stroke_width=router.WIRE_WIDTH + 1.5,
                fill="none", stroke_linejoin="round",
                stroke_linecap="round", opacity=0.15
            ))

            # Main wire
            wire_group.add(dwg.polyline(
                points=points,
                stroke=color, stroke_width=router.WIRE_WIDTH,
                fill="none", stroke_linejoin="round",
                stroke_linecap="round"
            ))

            # Highlight (thin lighter line on top for 3D wire effect)
            wire_group.add(dwg.polyline(
                points=points,
                stroke="#ffffff", stroke_width=0.6,
                fill="none", stroke_linejoin="round",
                stroke_linecap="round", opacity=0.2
            ))

            # ── Termination dots at endpoints ──
            for px, py in [path_points[0], path_points[-1]]:
                # Outer ring
                wire_group.add(dwg.circle(
                    center=(px, py), r=router.DOT_RADIUS,
                    fill=color, stroke="#fff",
                    stroke_width=0.8, opacity=0.9
                ))
                # Inner dot
                wire_group.add(dwg.circle(
                    center=(px, py), r=1.2,
                    fill="#ffffff", opacity=0.6
                ))

            # ── Optional wire label ──
            if wire.label:
                # Place label at midpoint of wire
                mid_idx = len(path_points) // 2
                lx, ly = path_points[mid_idx]
                wire_group.add(dwg.text(
                    wire.label,
                    insert=(lx + 4, ly - 4),
                    fill=color,
                    font_size="7px",
                    font_family="monospace",
                    font_weight="bold"
                ))

            g.add(wire_group)

    return g
