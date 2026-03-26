"""
components.py — Procedural SVG Component Library
=================================================
Each component is a class that can render itself as an SVG group
and expose pin anchor coordinates for wire routing.

Architecture note: Every component has BOTH a physical (breadboard)
representation and eventually a schematic symbol. The base class
enforces this dual-representation pattern for future extensibility.
"""

import svgwrite
from svgwrite import mm
from typing import Dict, Tuple, Optional


# ─── Color Palette ───────────────────────────────────────────────
# Fritzing-inspired but with richer tones
COLORS = {
    # PCB greens
    "pcb_dark":     "#1a6b3c",
    "pcb_mid":      "#2d8b57",
    "pcb_light":    "#3aaa6a",
    "pcb_mask":     "#1e7a45",
    # Arduino blue
    "arduino_blue": "#00878F",
    "arduino_dark": "#006C75",
    "arduino_light":"#00A0AA",
    # Breadboard
    "bb_white":     "#f0ece4",
    "bb_cream":     "#e8e0d0",
    "bb_rail_red":  "#d44040",
    "bb_rail_blue": "#3060c0",
    "bb_hole":      "#2a2a2a",
    "bb_hole_ring": "#888888",
    # Metal / pins
    "metal_silver": "#c0c0c0",
    "metal_dark":   "#707070",
    "metal_gold":   "#c8a84a",
    "pin_header":   "#333333",
    # Component body colors
    "ic_body":      "#303030",
    "pot_body":     "#8B7355",
    "pot_knob":     "#d0d0d0",
    "btn_body":     "#222222",
    "buzzer_body":  "#1a1a1a",
    "buzzer_top":   "#2a2a2a",
    "led_red":      "#ff2020",
    "led_pcb":      "#800000",
    "resistor_tan": "#d2b48c",
    # Text
    "label_dark":   "#222222",
    "label_light":  "#ffffff",
    "label_dim":    "#888888",
}


class Component:
    """Base class for all electronic components."""

    def __init__(self, comp_id: str, x: float, y: float):
        self.id = comp_id        # unique identifier (e.g., "uno", "bb")
        self.x = x               # top-left x position on canvas
        self.y = y               # top-left y position on canvas
        self.width = 0           # set by subclass
        self.height = 0          # set by subclass
        self._pins: Dict[str, Tuple[float, float]] = {}  # pin_name -> (abs_x, abs_y)

    def get_pin(self, pin_name: str) -> Tuple[float, float]:
        """Return absolute (x, y) coordinate of a named pin."""
        if pin_name not in self._pins:
            available = ", ".join(sorted(self._pins.keys()))
            raise ValueError(
                f"Component '{self.id}' has no pin '{pin_name}'. "
                f"Available: {available}"
            )
        return self._pins[pin_name]

    def get_all_pins(self) -> Dict[str, Tuple[float, float]]:
        return dict(self._pins)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        """Override in subclass. Returns an SVG group element."""
        raise NotImplementedError


class ArduinoUno(Component):
    """
    Arduino Uno R3 — top-down physical representation.
    Renders the blue PCB, USB port, barrel jack, pin headers,
    and all labeled pins with correct spacing.
    """

    # Physical dimensions (in SVG units ≈ pixels at 96dpi)
    W = 220
    H = 320

    # Pin header geometry — actual Arduino Uno has:
    # - Top header (digital): D0-D13 + GND + AREF + SDA + SCL (right side)
    # - Bottom header (power/analog): A0-A5, VIN, GND, GND, 5V, 3.3V, RESET (left side)
    PIN_SPACING = 14  # spacing between pin centers

    def __init__(self, comp_id: str, x: float, y: float):
        super().__init__(comp_id, x, y)
        self.width = self.W
        self.height = self.H
        self._compute_pins()

    def _compute_pins(self):
        """Calculate absolute positions for every Arduino Uno pin."""
        x, y = self.x, self.y
        ps = self.PIN_SPACING

        # ── Right-side header (Digital pins) ──
        # Pins run top-to-bottom on the right edge: D13 at top, D0 at bottom
        # Plus SCL, SDA, AREF, GND above D13
        right_x = x + self.W - 12  # pin center, inset from edge
        digital_start_y = y + 60   # first pin (SCL) vertical offset

        right_pins = ["SCL", "SDA", "AREF", "GND.2",
                       "13", "12", "11", "10", "9", "8",
                       # gap row
                       "7", "6", "5", "4", "3", "2", "1", "0"]

        for i, pin_name in enumerate(right_pins):
            # Small gap between pin 8 and pin 7 (the "~" gap on real board)
            gap = 8 if i >= 10 else 0
            self._pins[pin_name] = (right_x, digital_start_y + i * ps + gap)

        # ── Left-side header (Power + Analog) ──
        left_x = x + 12
        power_start_y = y + 172  # aligned with middle of board

        left_pins = ["A0", "A1", "A2", "A3", "A4", "A5",
                     # gap
                     "VIN", "GND.1", "GND.3", "5V", "3.3V", "RESET"]

        for i, pin_name in enumerate(left_pins):
            gap = 8 if i >= 6 else 0
            self._pins[pin_name] = (left_x, power_start_y + i * ps + gap)

        # ── USB port center (for reference/labeling) ──
        self._pins["USB"] = (x + self.W / 2, y + 8)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"comp_{self.id}")
        x, y, w, h = self.x, self.y, self.W, self.H

        # ── PCB Board ──
        # Main board with rounded corners
        g.add(dwg.rect(
            insert=(x, y), size=(w, h), rx=8, ry=8,
            fill=COLORS["arduino_blue"],
            stroke=COLORS["arduino_dark"], stroke_width=1.5
        ))
        # Subtle PCB texture — horizontal trace lines
        for ty in range(int(y) + 20, int(y + h) - 20, 6):
            g.add(dwg.line(
                start=(x + 20, ty), end=(x + w - 20, ty),
                stroke=COLORS["arduino_light"], stroke_width=0.3,
                opacity=0.15
            ))

        # ── Mounting holes (4 corners) ──
        for mx, my in [(x+14, y+14), (x+w-14, y+14),
                        (x+14, y+h-14), (x+w-14, y+h-14)]:
            g.add(dwg.circle(center=(mx, my), r=5,
                             fill="none", stroke=COLORS["metal_silver"],
                             stroke_width=1.5))
            g.add(dwg.circle(center=(mx, my), r=2,
                             fill=COLORS["metal_dark"]))

        # ── USB-B Port ──
        usb_w, usb_h = 44, 18
        usb_x = x + w/2 - usb_w/2
        usb_y = y + 2
        g.add(dwg.rect(
            insert=(usb_x, usb_y), size=(usb_w, usb_h), rx=2,
            fill=COLORS["metal_silver"],
            stroke=COLORS["metal_dark"], stroke_width=1
        ))
        # USB inner
        g.add(dwg.rect(
            insert=(usb_x + 6, usb_y + 3), size=(usb_w - 12, usb_h - 6),
            fill=COLORS["metal_dark"]
        ))

        # ── Barrel Jack ──
        jack_x = x + 4
        jack_y = y + 4
        g.add(dwg.rect(
            insert=(jack_x, jack_y), size=(14, 30), rx=2,
            fill=COLORS["ic_body"],
            stroke=COLORS["metal_dark"], stroke_width=0.8
        ))
        g.add(dwg.circle(center=(jack_x + 7, jack_y + 15), r=4,
                         fill=COLORS["metal_dark"]))

        # ── Reset Button ──
        btn_cx = x + w/2 + 30
        btn_cy = y + 40
        g.add(dwg.circle(center=(btn_cx, btn_cy), r=6,
                         fill=COLORS["metal_silver"],
                         stroke=COLORS["metal_dark"], stroke_width=1))
        g.add(dwg.circle(center=(btn_cx, btn_cy), r=3.5,
                         fill="#cc4444"))

        # ── ATmega328P IC ──
        ic_w, ic_h = 50, 70
        ic_x = x + w/2 - ic_w/2
        ic_y = y + h/2 - ic_h/2 + 10
        g.add(dwg.rect(
            insert=(ic_x, ic_y), size=(ic_w, ic_h), rx=1,
            fill=COLORS["ic_body"],
            stroke=COLORS["metal_dark"], stroke_width=0.5
        ))
        # IC notch
        g.add(dwg.circle(center=(ic_x + ic_w/2, ic_y + 3), r=4,
                         fill=COLORS["metal_dark"]))
        # IC pin legs
        for p in range(14):
            # left side pins
            py = ic_y + 5 + p * (ic_h - 10) / 13
            g.add(dwg.line(start=(ic_x - 4, py), end=(ic_x, py),
                           stroke=COLORS["metal_silver"], stroke_width=1.2))
            # right side pins
            g.add(dwg.line(start=(ic_x + ic_w, py), end=(ic_x + ic_w + 4, py),
                           stroke=COLORS["metal_silver"], stroke_width=1.2))

        # ── LEDs (TX, RX, Power, L) ──
        led_data = [
            (x + w/2 - 20, y + 50, "#ff4444", "TX"),
            (x + w/2 - 8,  y + 50, "#44ff44", "RX"),
            (x + w/2 + 8,  y + 50, "#44ff44", "PWR"),
            (x + w/2 + 20, y + 50, "#ffaa00", "L"),
        ]
        for lx, ly, color, label in led_data:
            # LED glow
            g.add(dwg.circle(center=(lx, ly), r=4,
                             fill=color, opacity=0.3))
            g.add(dwg.circle(center=(lx, ly), r=2,
                             fill=color))

        # ── Pin Headers ──
        # Draw black header strips and individual gold pins
        for pin_name, (px, py) in self._pins.items():
            if pin_name == "USB":
                continue  # not a real pin

            # Pin hole (gold contact in black header)
            g.add(dwg.rect(
                insert=(px - 4, py - 4), size=(8, 8), rx=1,
                fill=COLORS["pin_header"]
            ))
            g.add(dwg.circle(center=(px, py), r=2.2,
                             fill=COLORS["metal_gold"]))

        # ── Pin Labels ──
        # Labels are placed INSIDE the board (like silkscreen)
        for pin_name, (px, py) in self._pins.items():
            if pin_name == "USB":
                continue
            is_right = px > self.x + self.W / 2
            # Place label inward from the pin, like real PCB silkscreen
            label_x = px - 12 if is_right else px + 12
            anchor = "end" if is_right else "start"

            display_name = pin_name.replace("GND.1", "GND").replace("GND.2", "GND").replace("GND.3", "GND")

            # Tilde prefix for PWM pins
            if display_name in ["3", "5", "6", "9", "10", "11"]:
                display_name = "~" + display_name

            g.add(dwg.text(
                display_name,
                insert=(label_x, py + 3),
                fill=COLORS["label_light"],
                font_size="6.5px",
                font_family="'Consolas', 'Monaco', monospace",
                text_anchor=anchor,
                opacity=0.85
            ))

        # ── Board Labels ──
        g.add(dwg.text(
            "ARDUINO",
            insert=(x + w/2, y + h - 30),
            fill=COLORS["label_light"],
            font_size="14px",
            font_family="'Arial Black', 'Helvetica', sans-serif",
            font_weight="bold",
            text_anchor="middle",
            opacity=0.8
        ))
        g.add(dwg.text(
            "UNO",
            insert=(x + w/2, y + h - 16),
            fill=COLORS["label_light"],
            font_size="11px",
            font_family="'Arial Black', 'Helvetica', sans-serif",
            text_anchor="middle",
            opacity=0.6
        ))

        return g


class Breadboard(Component):
    """
    Half-size solderless breadboard — 30 columns, 5-row sections (a-e, f-j),
    plus top and bottom power rails (+/-).

    Pin naming convention:
    - Power rails: "tp.N" (top positive), "tn.N" (top negative),
                   "bp.N" (bottom positive), "bn.N" (bottom negative)
    - Main grid:   "a1" through "j30" (row letter + column number)
    """

    COLS = 30
    HOLE_SPACING = 11      # px between hole centers
    HOLE_R = 2.2           # hole radius
    RAIL_OFFSET = 14       # vertical offset for rail rows from board edge
    SECTION_GAP = 18       # gap between top section (a-e) and bottom section (f-j)
    MARGIN_X = 22          # horizontal margin inside board
    MARGIN_TOP = 42        # space for top rail + gap before main grid

    def __init__(self, comp_id: str, x: float, y: float):
        super().__init__(comp_id, x, y)
        self.width = self.MARGIN_X * 2 + (self.COLS - 1) * self.HOLE_SPACING
        self.height = (self.MARGIN_TOP + 10 * self.HOLE_SPACING +
                       self.SECTION_GAP + self.MARGIN_TOP)
        self._compute_pins()

    def _col_x(self, col: int) -> float:
        """X coordinate for a given column (1-indexed)."""
        return self.x + self.MARGIN_X + (col - 1) * self.HOLE_SPACING

    def _compute_pins(self):
        x, y = self.x, self.y
        hs = self.HOLE_SPACING

        # ── Top power rails ──
        # Two rows: positive (red) and negative (blue)
        rail_top_y_pos = y + self.RAIL_OFFSET
        rail_top_y_neg = y + self.RAIL_OFFSET + hs

        for col in range(1, self.COLS + 1):
            cx = self._col_x(col)
            self._pins[f"tp.{col}"] = (cx, rail_top_y_pos)
            self._pins[f"tn.{col}"] = (cx, rail_top_y_neg)

        # ── Main grid ──
        # Top section: rows a-e (5 rows)
        grid_start_y = y + self.MARGIN_TOP
        rows_top = "abcde"
        for ri, row_letter in enumerate(rows_top):
            for col in range(1, self.COLS + 1):
                cx = self._col_x(col)
                cy = grid_start_y + ri * hs
                self._pins[f"{row_letter}{col}"] = (cx, cy)

        # Bottom section: rows f-j (5 rows), offset by section gap
        grid_bottom_y = grid_start_y + 5 * hs + self.SECTION_GAP
        rows_bottom = "fghij"
        for ri, row_letter in enumerate(rows_bottom):
            for col in range(1, self.COLS + 1):
                cx = self._col_x(col)
                cy = grid_bottom_y + ri * hs
                self._pins[f"{row_letter}{col}"] = (cx, cy)

        # ── Bottom power rails ──
        rail_bot_y_pos = grid_bottom_y + 5 * hs + 16
        rail_bot_y_neg = rail_bot_y_pos + hs

        for col in range(1, self.COLS + 1):
            cx = self._col_x(col)
            self._pins[f"bp.{col}"] = (cx, rail_bot_y_pos)
            self._pins[f"bn.{col}"] = (cx, rail_bot_y_neg)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"comp_{self.id}")
        x, y, w, h = self.x, self.y, self.width, self.height

        # ── Board body ──
        g.add(dwg.rect(
            insert=(x, y), size=(w, h), rx=4, ry=4,
            fill=COLORS["bb_white"],
            stroke="#bbb", stroke_width=1
        ))

        # ── Subtle board texture ──
        for ty in range(int(y) + 4, int(y + h) - 4, 3):
            g.add(dwg.line(
                start=(x + 4, ty), end=(x + w - 4, ty),
                stroke="#ddd8d0", stroke_width=0.3, opacity=0.5
            ))

        # ── Power rail color strips ──
        hs = self.HOLE_SPACING
        strip_h = 4

        # Top positive rail (red strip)
        tp_y = y + self.RAIL_OFFSET
        g.add(dwg.rect(
            insert=(x + 8, tp_y - strip_h/2 - hs*0.3),
            size=(w - 16, strip_h), rx=1,
            fill=COLORS["bb_rail_red"], opacity=0.6
        ))
        g.add(dwg.text("+", insert=(x + 4, tp_y + 3),
                        fill=COLORS["bb_rail_red"], font_size="9px",
                        font_weight="bold", font_family="sans-serif"))

        # Top negative rail (blue strip)
        tn_y = y + self.RAIL_OFFSET + hs
        g.add(dwg.rect(
            insert=(x + 8, tn_y - strip_h/2 + hs*0.3),
            size=(w - 16, strip_h), rx=1,
            fill=COLORS["bb_rail_blue"], opacity=0.6
        ))
        g.add(dwg.text("–", insert=(x + 4, tn_y + 3),
                        fill=COLORS["bb_rail_blue"], font_size="9px",
                        font_weight="bold", font_family="sans-serif"))

        # Bottom rails (same pattern)
        grid_bottom_y = y + self.MARGIN_TOP + 5 * hs + self.SECTION_GAP
        bp_y = grid_bottom_y + 5 * hs + 16
        bn_y = bp_y + hs

        g.add(dwg.rect(
            insert=(x + 8, bp_y - strip_h/2 - hs*0.3),
            size=(w - 16, strip_h), rx=1,
            fill=COLORS["bb_rail_red"], opacity=0.6
        ))
        g.add(dwg.text("+", insert=(x + 4, bp_y + 3),
                        fill=COLORS["bb_rail_red"], font_size="9px",
                        font_weight="bold", font_family="sans-serif"))

        g.add(dwg.rect(
            insert=(x + 8, bn_y - strip_h/2 + hs*0.3),
            size=(w - 16, strip_h), rx=1,
            fill=COLORS["bb_rail_blue"], opacity=0.6
        ))
        g.add(dwg.text("–", insert=(x + 4, bn_y + 3),
                        fill=COLORS["bb_rail_blue"], font_size="9px",
                        font_weight="bold", font_family="sans-serif"))

        # ── Center divider groove ──
        groove_y = y + self.MARGIN_TOP + 5 * hs
        g.add(dwg.rect(
            insert=(x + 8, groove_y),
            size=(w - 16, self.SECTION_GAP),
            fill=COLORS["bb_cream"], rx=2
        ))
        # Groove notch line
        g.add(dwg.line(
            start=(x + 12, groove_y + self.SECTION_GAP / 2),
            end=(x + w - 12, groove_y + self.SECTION_GAP / 2),
            stroke="#c0b8a8", stroke_width=1.5
        ))

        # ── Column numbers ──
        # Label every 5th column along top
        for col in [1, 5, 10, 15, 20, 25, 30]:
            cx = self._col_x(col)
            g.add(dwg.text(
                str(col), insert=(cx, y + self.MARGIN_TOP - 8),
                fill=COLORS["label_dim"],
                font_size="6px", font_family="monospace",
                text_anchor="middle"
            ))

        # ── Row letters ──
        grid_start_y = y + self.MARGIN_TOP
        for ri, letter in enumerate("abcde"):
            ry = grid_start_y + ri * hs
            g.add(dwg.text(
                letter, insert=(x + 12, ry + 3),
                fill=COLORS["label_dim"],
                font_size="6px", font_family="monospace",
                text_anchor="middle"
            ))

        grid_bottom_start = grid_start_y + 5 * hs + self.SECTION_GAP
        for ri, letter in enumerate("fghij"):
            ry = grid_bottom_start + ri * hs
            g.add(dwg.text(
                letter, insert=(x + 12, ry + 3),
                fill=COLORS["label_dim"],
                font_size="6px", font_family="monospace",
                text_anchor="middle"
            ))

        # ── Holes ──
        # All holes: power rails + main grid
        for pin_name, (px, py) in self._pins.items():
            # Outer ring (metal contact)
            g.add(dwg.circle(center=(px, py), r=self.HOLE_R + 0.8,
                             fill=COLORS["bb_hole_ring"], opacity=0.3))
            # Hole itself
            g.add(dwg.circle(center=(px, py), r=self.HOLE_R,
                             fill=COLORS["bb_hole"]))

        return g


class MAX7219Matrix(Component):
    """
    MAX7219 8x8 LED Matrix module.
    Red PCB with 8x8 grid of LEDs and 5-pin header (VCC, GND, DIN, CS, CLK).
    """

    W = 70
    H = 90

    def __init__(self, comp_id: str, x: float, y: float, color: str = "red"):
        super().__init__(comp_id, x, y)
        self.width = self.W
        self.height = self.H
        self.led_color = color
        self._compute_pins()

    def _compute_pins(self):
        x, y = self.x, self.y
        # 5-pin header at the bottom of the module
        # Pin order left to right: VCC, GND, DIN, CS, CLK
        pin_names = ["VCC", "GND", "DIN", "CS", "CLK"]
        pin_spacing = 13  # wider spacing for label readability
        start_x = x + self.W / 2 - (len(pin_names) - 1) * pin_spacing / 2

        for i, name in enumerate(pin_names):
            self._pins[name] = (start_x + i * pin_spacing, y + self.H + 4)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"comp_{self.id}")
        x, y, w, h = self.x, self.y, self.W, self.H

        # ── PCB body ──
        g.add(dwg.rect(
            insert=(x, y), size=(w, h), rx=3,
            fill=COLORS["led_pcb"],
            stroke="#600", stroke_width=1
        ))

        # ── LED matrix housing (black square with grid) ──
        matrix_size = 55
        mx = x + w/2 - matrix_size/2
        my = y + 8
        g.add(dwg.rect(
            insert=(mx, my), size=(matrix_size, matrix_size), rx=2,
            fill="#111", stroke="#333", stroke_width=0.5
        ))

        # ── 8x8 LED grid ──
        led_spacing = matrix_size / 9
        for row in range(8):
            for col in range(8):
                lx = mx + led_spacing * (col + 1)
                ly = my + led_spacing * (row + 1)
                # LED diffuser circle
                led_c = COLORS["led_red"] if self.led_color == "red" else "#40ff40"
                g.add(dwg.circle(center=(lx, ly), r=2.5,
                                 fill=led_c, opacity=0.7))
                g.add(dwg.circle(center=(lx, ly), r=1.5,
                                 fill=led_c, opacity=0.9))

        # ── Pin header at bottom ──
        for name, (px, py) in self._pins.items():
            g.add(dwg.rect(
                insert=(px - 4, py - 6), size=(8, 10), rx=1,
                fill=COLORS["pin_header"]
            ))
            g.add(dwg.circle(center=(px, py - 1), r=1.8,
                             fill=COLORS["metal_gold"]))
            # Pin label — angled for readability
            label_elem = dwg.text(
                name, insert=(px, py + 14),
                fill=COLORS["label_dark"],
                font_size="6px", font_family="monospace",
                text_anchor="start",
                transform=f"rotate(45, {px}, {py + 14})"
            )
            g.add(label_elem)

        # ── Module label ──
        g.add(dwg.text(
            "MAX7219", insert=(x + w/2, y + h - 10),
            fill=COLORS["label_light"],
            font_size="7px", font_family="monospace",
            text_anchor="middle", opacity=0.7
        ))

        return g


class Potentiometer(Component):
    """
    10K rotary potentiometer — 3-pin through-hole.
    Pins: 1 (outer/VCC), 2 (wiper/signal), 3 (outer/GND)
    """

    W = 40
    H = 44

    def __init__(self, comp_id: str, x: float, y: float):
        super().__init__(comp_id, x, y)
        self.width = self.W
        self.height = self.H
        self._compute_pins()

    def _compute_pins(self):
        x, y = self.x, self.y
        # 3 pins at the bottom, evenly spaced
        pin_spacing = 11
        cx = x + self.W / 2
        self._pins["1"] = (cx - pin_spacing, y + self.H + 4)  # VCC side
        self._pins["2"] = (cx, y + self.H + 4)                 # Wiper
        self._pins["3"] = (cx + pin_spacing, y + self.H + 4)   # GND side

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"comp_{self.id}")
        x, y, w, h = self.x, self.y, self.W, self.H

        # ── Body (cylindrical from top) ──
        cx, cy = x + w/2, y + h/2
        # Outer ring
        g.add(dwg.circle(center=(cx, cy), r=18,
                         fill=COLORS["pot_body"],
                         stroke="#5a4a3a", stroke_width=1.5))
        # Grip ridges (radial lines)
        import math
        for angle in range(0, 360, 20):
            rad = math.radians(angle)
            g.add(dwg.line(
                start=(cx + 14 * math.cos(rad), cy + 14 * math.sin(rad)),
                end=(cx + 18 * math.cos(rad), cy + 18 * math.sin(rad)),
                stroke="#6a5a4a", stroke_width=0.8
            ))

        # Knob center
        g.add(dwg.circle(center=(cx, cy), r=8,
                         fill=COLORS["pot_knob"],
                         stroke="#aaa", stroke_width=0.8))
        # Knob indicator line
        g.add(dwg.line(start=(cx, cy - 8), end=(cx, cy - 3),
                       stroke=COLORS["metal_dark"], stroke_width=1.5))

        # ── Pin legs ──
        for name, (px, py) in self._pins.items():
            g.add(dwg.rect(
                insert=(px - 2, py - 6), size=(4, 10), rx=0.5,
                fill=COLORS["metal_silver"]
            ))

        # ── Label ──
        g.add(dwg.text(
            "10K", insert=(cx, y + h + 18),
            fill=COLORS["label_dark"],
            font_size="6px", font_family="monospace",
            text_anchor="middle"
        ))

        return g


class PushButton(Component):
    """
    Tactile push button — 4-pin, straddles breadboard center gap.
    We expose just the 2 logical sides:
    Pin 1 (top-left pair) and Pin 2 (bottom-left pair).
    For breadboard use: "1.1"/"1.2" and "2.1"/"2.2"
    """

    W = 24
    H = 24

    def __init__(self, comp_id: str, x: float, y: float, color: str = "red"):
        super().__init__(comp_id, x, y)
        self.width = self.W
        self.height = self.H
        self.btn_color = color
        self._compute_pins()

    def _compute_pins(self):
        x, y = self.x, self.y
        # 4 legs, one at each corner
        self._pins["1.1"] = (x + 2, y + self.H + 4)        # top-left
        self._pins["1.2"] = (x + self.W - 2, y + self.H + 4)  # top-right
        self._pins["2.1"] = (x + 2, y - 4)                  # bottom-left
        self._pins["2.2"] = (x + self.W - 2, y - 4)         # bottom-right

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"comp_{self.id}")
        x, y, w, h = self.x, self.y, self.W, self.H

        # ── Body ──
        g.add(dwg.rect(
            insert=(x, y), size=(w, h), rx=2,
            fill=COLORS["btn_body"],
            stroke="#444", stroke_width=0.8
        ))

        # ── Button cap ──
        cx, cy = x + w/2, y + h/2
        cap_colors = {"red": "#cc3333", "green": "#33aa33",
                      "blue": "#3355cc", "yellow": "#ccaa22"}
        cap_c = cap_colors.get(self.btn_color, "#cc3333")

        g.add(dwg.circle(center=(cx, cy), r=8,
                         fill=cap_c, stroke="#222", stroke_width=0.5))
        # Highlight
        g.add(dwg.circle(center=(cx - 2, cy - 2), r=3,
                         fill="#ffffff", opacity=0.2))

        # ── Pin legs ──
        for name, (px, py) in self._pins.items():
            g.add(dwg.rect(
                insert=(px - 1.5, min(py, y) - 2),
                size=(3, 8), rx=0.3,
                fill=COLORS["metal_silver"]
            ))

        return g


class PiezoBuzzer(Component):
    """
    Piezo buzzer — cylindrical, 2 pins (positive, negative).
    """

    W = 40
    H = 40

    def __init__(self, comp_id: str, x: float, y: float):
        super().__init__(comp_id, x, y)
        self.width = self.W
        self.height = self.H
        self._compute_pins()

    def _compute_pins(self):
        x, y = self.x, self.y
        cx = x + self.W / 2
        # Two pins at bottom, spaced apart
        self._pins["1"] = (cx - 6, y + self.H + 4)   # negative (-)
        self._pins["2"] = (cx + 6, y + self.H + 4)   # positive (+)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"comp_{self.id}")
        x, y, w, h = self.x, self.y, self.W, self.H
        cx, cy = x + w/2, y + h/2

        # ── Body (cylindrical top-down) ──
        g.add(dwg.circle(center=(cx, cy), r=18,
                         fill=COLORS["buzzer_body"],
                         stroke="#333", stroke_width=1.2))
        # Sound hole
        g.add(dwg.circle(center=(cx, cy), r=4,
                         fill=COLORS["buzzer_top"],
                         stroke="#444", stroke_width=0.5))
        # Sound ring pattern
        for r in [8, 12, 15]:
            g.add(dwg.circle(center=(cx, cy), r=r,
                             fill="none", stroke="#333",
                             stroke_width=0.4, opacity=0.5))

        # ── Polarity marking ──
        g.add(dwg.text("+", insert=(cx + 8, y + 6),
                        fill=COLORS["label_light"],
                        font_size="8px", font_weight="bold",
                        font_family="sans-serif"))

        # ── Pin legs ──
        for name, (px, py) in self._pins.items():
            g.add(dwg.rect(
                insert=(px - 1.5, py - 6), size=(3, 10), rx=0.3,
                fill=COLORS["metal_silver"]
            ))
            label = "+" if name == "2" else "–"
            g.add(dwg.text(
                label, insert=(px, py + 12),
                fill=COLORS["label_dark"],
                font_size="6px", font_family="sans-serif",
                text_anchor="middle"
            ))

        return g


class Battery9V(Component):
    """
    9V battery with snap connector — 2 pins (positive, negative).
    """

    W = 50
    H = 70

    def __init__(self, comp_id: str, x: float, y: float):
        super().__init__(comp_id, x, y)
        self.width = self.W
        self.height = self.H
        self._compute_pins()

    def _compute_pins(self):
        x, y = self.x, self.y
        # Wires come out the top
        cx = x + self.W / 2
        self._pins["+"] = (cx + 8, y - 4)
        self._pins["-"] = (cx - 8, y - 4)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"comp_{self.id}")
        x, y, w, h = self.x, self.y, self.W, self.H

        # ── Battery body ──
        g.add(dwg.rect(
            insert=(x, y), size=(w, h), rx=4,
            fill="#444",
            stroke="#333", stroke_width=1
        ))
        # Label area
        g.add(dwg.rect(
            insert=(x + 4, y + 10), size=(w - 8, h - 20), rx=2,
            fill="#666"
        ))
        g.add(dwg.text(
            "9V", insert=(x + w/2, y + h/2 + 4),
            fill=COLORS["label_light"],
            font_size="14px", font_weight="bold",
            font_family="sans-serif",
            text_anchor="middle"
        ))

        # ── Snap connector terminals at top ──
        # Positive (smaller, round)
        px_pos = x + w/2 + 8
        g.add(dwg.circle(center=(px_pos, y + 4), r=4,
                         fill=COLORS["metal_silver"],
                         stroke="#999", stroke_width=0.5))
        g.add(dwg.text("+", insert=(px_pos + 8, y + 6),
                        fill=COLORS["bb_rail_red"],
                        font_size="8px", font_weight="bold"))

        # Negative (larger, also round for simplicity)
        px_neg = x + w/2 - 8
        g.add(dwg.circle(center=(px_neg, y + 4), r=5,
                         fill=COLORS["metal_silver"],
                         stroke="#999", stroke_width=0.5))
        g.add(dwg.text("–", insert=(px_neg - 14, y + 6),
                        fill=COLORS["bb_rail_blue"],
                        font_size="8px", font_weight="bold"))

        return g


class RaspberryPi(Component):
    """
    Raspberry Pi 3/4 — simplified top-down view showing USB port
    for serial connection to Arduino. Only exposes USB as a pin
    since the connection is just a USB cable in this project.
    """

    W = 180
    H = 120

    def __init__(self, comp_id: str, x: float, y: float):
        super().__init__(comp_id, x, y)
        self.width = self.W
        self.height = self.H
        self._compute_pins()

    def _compute_pins(self):
        x, y = self.x, self.y
        # USB ports on the right side
        self._pins["USB1"] = (x + self.W, y + 30)
        self._pins["USB2"] = (x + self.W, y + 55)
        self._pins["USB3"] = (x + self.W, y + 75)
        self._pins["USB4"] = (x + self.W, y + 95)
        # GPIO header (simplified — just expose useful pins)
        # 40-pin header along the top edge
        for i in range(20):
            self._pins[f"GPIO_{i+1}"] = (x + 30 + i * 6, y)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"comp_{self.id}")
        x, y, w, h = self.x, self.y, self.W, self.H

        # ── PCB ──
        g.add(dwg.rect(
            insert=(x, y), size=(w, h), rx=4,
            fill=COLORS["pcb_dark"],
            stroke=COLORS["pcb_mid"], stroke_width=1.5
        ))

        # PCB trace texture
        for ty in range(int(y) + 10, int(y + h) - 10, 5):
            g.add(dwg.line(
                start=(x + 10, ty), end=(x + w - 10, ty),
                stroke=COLORS["pcb_light"], stroke_width=0.2, opacity=0.15
            ))

        # ── SoC (big silver square) ──
        soc_size = 40
        g.add(dwg.rect(
            insert=(x + 30, y + h/2 - soc_size/2),
            size=(soc_size, soc_size), rx=2,
            fill=COLORS["metal_silver"],
            stroke=COLORS["metal_dark"], stroke_width=0.8
        ))

        # ── USB ports (right edge) ──
        for port_name in ["USB1", "USB2", "USB3", "USB4"]:
            _, py = self._pins[port_name]
            usb_w, usb_h = 18, 16
            g.add(dwg.rect(
                insert=(x + w - 4, py - usb_h/2),
                size=(usb_w, usb_h), rx=1,
                fill=COLORS["metal_silver"],
                stroke=COLORS["metal_dark"], stroke_width=0.8
            ))

        # ── Ethernet port ──
        g.add(dwg.rect(
            insert=(x + w - 4, y + 5), size=(18, 18), rx=1,
            fill=COLORS["metal_silver"],
            stroke=COLORS["metal_dark"], stroke_width=0.8
        ))

        # ── GPIO header strip ──
        gpio_x = x + 28
        gpio_y = y + 4
        g.add(dwg.rect(
            insert=(gpio_x - 2, gpio_y - 2),
            size=(20 * 6 + 4, 10), rx=1,
            fill=COLORS["pin_header"]
        ))
        for i in range(20):
            px = gpio_x + i * 6
            # Two rows of pins
            g.add(dwg.circle(center=(px, gpio_y + 2), r=1.2,
                             fill=COLORS["metal_gold"]))
            g.add(dwg.circle(center=(px, gpio_y + 6), r=1.2,
                             fill=COLORS["metal_gold"]))

        # ── Raspberry Pi logo area ──
        g.add(dwg.text(
            "Raspberry Pi",
            insert=(x + w/2 - 20, y + h - 12),
            fill=COLORS["label_light"],
            font_size="10px",
            font_family="'Arial', sans-serif",
            font_weight="bold",
            opacity=0.8
        ))

        # ── Mounting holes ──
        for mx, my in [(x+4, y+4), (x+w-4, y+4),
                        (x+4, y+h-4), (x+w-4, y+h-4)]:
            g.add(dwg.circle(center=(mx, my), r=3,
                             fill="none", stroke=COLORS["metal_silver"],
                             stroke_width=1))

        return g


# ─── Component Registry ─────────────────────────────────────────
# Maps type strings (from diagram.json) to component classes
COMPONENT_REGISTRY = {
    "arduino-uno":      ArduinoUno,
    "breadboard":       Breadboard,
    "max7219-matrix":   MAX7219Matrix,
    "potentiometer":    Potentiometer,
    "pushbutton":       PushButton,
    "piezo-buzzer":     PiezoBuzzer,
    "battery-9v":       Battery9V,
    "raspberry-pi":     RaspberryPi,
}
