"""
schematic.py — Schematic Symbol Renderer
=========================================
Renders electronic schematics using IEEE/ANSI-style symbols.
Each component has a rectangular or standard symbol with labeled
pins, connected by straight-line nets with labels.

Schematic diagrams show LOGICAL connections (what connects to what)
rather than PHYSICAL layout (where things sit on a breadboard).
This is the complement to the breadboard renderer in components.py.

Usage: The main CLI calls generate_schematic() instead of
generate_diagram() when --mode schematic is specified. Same JSON
config, different visual output.
"""

import svgwrite
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


# ─── Schematic Color Palette ─────────────────────────────────────
# Clean, technical drawing aesthetic
SCH_COLORS = {
    "bg":           "#ffffff",
    "component":    "#000000",   # component outlines
    "fill":         "#fffde8",   # component fill (pale yellow)
    "pin":          "#000000",   # pin stubs
    "pin_label":    "#0055aa",   # pin name text
    "wire":         "#006600",   # net wires (green like EDA tools)
    "power_wire":   "#cc0000",   # power nets
    "ground_wire":  "#000000",   # ground nets
    "net_label":    "#880088",   # net label text (purple)
    "value":        "#666666",   # component value text
    "refdes":       "#000000",   # reference designator (U1, R1, etc.)
    "title":        "#000000",
    "grid":         "#e8e8e8",   # background grid
    "border":       "#000000",
}

# Standard schematic pin spacing (multiples of grid)
GRID = 10           # base grid unit in pixels
PIN_LENGTH = 30     # length of pin stub lines
PIN_SPACING = 20    # vertical space between pins
COMP_PADDING = 15   # internal padding inside component box


@dataclass
class SchPin:
    """A pin on a schematic symbol with position and metadata."""
    name: str
    x: float           # absolute x after placement
    y: float           # absolute y after placement
    side: str           # "left", "right", "top", "bottom"
    pin_type: str = ""  # "power", "ground", "input", "output", "bidirectional"


class SchematicSymbol:
    """
    Base class for schematic symbols.
    Each symbol is a rectangular box with pins on the sides,
    plus optional special drawing for standard symbols
    (resistor zigzag, capacitor plates, etc.).
    """

    def __init__(self, comp_id: str, ref_des: str, x: float, y: float):
        self.id = comp_id
        self.ref_des = ref_des   # e.g., "U1", "R1", "SW1"
        self.x = x
        self.y = y
        self.width = 0
        self.height = 0
        self.pins: Dict[str, SchPin] = {}
        self.value = ""          # e.g., "10K", "ATmega328P"

    def get_pin(self, pin_name: str) -> Tuple[float, float]:
        if pin_name not in self.pins:
            available = ", ".join(sorted(self.pins.keys()))
            raise ValueError(
                f"Schematic symbol '{self.id}' has no pin '{pin_name}'. "
                f"Available: {available}"
            )
        p = self.pins[pin_name]
        return (p.x, p.y)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        raise NotImplementedError


class MCUSymbol(SchematicSymbol):
    """
    Microcontroller schematic symbol — large rectangle with
    many pins on left and right sides. Used for Arduino, Raspberry Pi,
    and similar multi-pin ICs.
    """

    def __init__(self, comp_id: str, ref_des: str, x: float, y: float,
                 left_pins: List[Tuple[str, str]],
                 right_pins: List[Tuple[str, str]],
                 value: str = ""):
        super().__init__(comp_id, ref_des, x, y)
        self.value = value

        # Calculate dimensions based on pin count
        max_pins = max(len(left_pins), len(right_pins))
        self.width = 160
        self.height = max(max_pins * PIN_SPACING + COMP_PADDING * 2, 80)

        # Place left-side pins (inputs typically)
        for i, (name, ptype) in enumerate(left_pins):
            py = y + COMP_PADDING + i * PIN_SPACING + PIN_SPACING // 2
            px = x - PIN_LENGTH  # pin endpoint extends left of box
            self.pins[name] = SchPin(name, px, py, "left", ptype)

        # Place right-side pins (outputs typically)
        for i, (name, ptype) in enumerate(right_pins):
            py = y + COMP_PADDING + i * PIN_SPACING + PIN_SPACING // 2
            px = x + self.width + PIN_LENGTH  # extends right of box
            self.pins[name] = SchPin(name, px, py, "right", ptype)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"sch_{self.id}")
        x, y, w, h = self.x, self.y, self.width, self.height

        # Component body rectangle
        g.add(dwg.rect(
            insert=(x, y), size=(w, h),
            fill=SCH_COLORS["fill"],
            stroke=SCH_COLORS["component"],
            stroke_width=2
        ))

        # Reference designator (above the box)
        g.add(dwg.text(
            self.ref_des, insert=(x + w / 2, y - 8),
            fill=SCH_COLORS["refdes"],
            font_size="12px", font_family="monospace",
            font_weight="bold", text_anchor="middle"
        ))

        # Value label (below the box)
        if self.value:
            g.add(dwg.text(
                self.value, insert=(x + w / 2, y + h + 16),
                fill=SCH_COLORS["value"],
                font_size="10px", font_family="monospace",
                text_anchor="middle"
            ))

        # Draw pins and labels
        for name, pin in self.pins.items():
            if pin.side == "left":
                # Pin stub: from pin endpoint to box edge
                g.add(dwg.line(
                    start=(pin.x, pin.y), end=(x, pin.y),
                    stroke=SCH_COLORS["pin"], stroke_width=1.5
                ))
                # Pin dot at endpoint
                g.add(dwg.circle(
                    center=(pin.x, pin.y), r=2.5,
                    fill=SCH_COLORS["pin"]
                ))
                # Pin label inside box
                g.add(dwg.text(
                    name, insert=(x + 6, pin.y + 4),
                    fill=SCH_COLORS["pin_label"],
                    font_size="9px", font_family="monospace"
                ))
            elif pin.side == "right":
                g.add(dwg.line(
                    start=(x + w, pin.y), end=(pin.x, pin.y),
                    stroke=SCH_COLORS["pin"], stroke_width=1.5
                ))
                g.add(dwg.circle(
                    center=(pin.x, pin.y), r=2.5,
                    fill=SCH_COLORS["pin"]
                ))
                g.add(dwg.text(
                    name, insert=(x + w - 6, pin.y + 4),
                    fill=SCH_COLORS["pin_label"],
                    font_size="9px", font_family="monospace",
                    text_anchor="end"
                ))

        return g


class PassiveSymbol(SchematicSymbol):
    """
    Standard schematic symbol for passive components:
    resistors (zigzag), potentiometers (zigzag + arrow),
    capacitors, etc. Drawn with standard IEEE shapes.
    """

    def __init__(self, comp_id: str, ref_des: str, x: float, y: float,
                 symbol_type: str = "resistor", value: str = "",
                 pin_names: Tuple[str, str] = ("1", "2"),
                 extra_pin: Optional[str] = None):
        super().__init__(comp_id, ref_des, x, y)
        self.symbol_type = symbol_type
        self.value = value
        self.width = 80
        self.height = 30

        # Two main pins (left and right)
        self.pins[pin_names[0]] = SchPin(pin_names[0], x - PIN_LENGTH, y + self.height // 2, "left")
        self.pins[pin_names[1]] = SchPin(pin_names[1], x + self.width + PIN_LENGTH, y + self.height // 2, "right")

        # Optional third pin (potentiometer wiper)
        if extra_pin:
            self.pins[extra_pin] = SchPin(extra_pin, x + self.width // 2, y + self.height + PIN_LENGTH, "bottom")

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"sch_{self.id}")
        x, y, w, h = self.x, self.y, self.width, self.height
        cy = y + h // 2  # center y

        # Reference designator
        g.add(dwg.text(
            self.ref_des, insert=(x + w / 2, y - 8),
            fill=SCH_COLORS["refdes"],
            font_size="10px", font_family="monospace",
            font_weight="bold", text_anchor="middle"
        ))

        # Value
        if self.value:
            g.add(dwg.text(
                self.value, insert=(x + w / 2, y + h + 14),
                fill=SCH_COLORS["value"],
                font_size="9px", font_family="monospace",
                text_anchor="middle"
            ))

        if self.symbol_type == "resistor":
            self._draw_resistor(dwg, g, x, cy, w)
        elif self.symbol_type == "potentiometer":
            self._draw_resistor(dwg, g, x, cy, w)
            self._draw_wiper_arrow(dwg, g, x + w // 2, cy)
        elif self.symbol_type == "capacitor":
            self._draw_capacitor(dwg, g, x, cy, w)
        elif self.symbol_type == "switch":
            self._draw_switch(dwg, g, x, cy, w)
        elif self.symbol_type == "buzzer":
            self._draw_buzzer_symbol(dwg, g, x, y, w, h)
        else:
            # Generic box fallback
            g.add(dwg.rect(insert=(x, y), size=(w, h),
                           fill=SCH_COLORS["fill"],
                           stroke=SCH_COLORS["component"], stroke_width=1.5))

        # Draw pin stubs for all pins
        for name, pin in self.pins.items():
            if pin.side == "left":
                g.add(dwg.line(start=(pin.x, pin.y), end=(x, pin.y),
                               stroke=SCH_COLORS["pin"], stroke_width=1.5))
                g.add(dwg.circle(center=(pin.x, pin.y), r=2.5, fill=SCH_COLORS["pin"]))
            elif pin.side == "right":
                g.add(dwg.line(start=(x + w, pin.y), end=(pin.x, pin.y),
                               stroke=SCH_COLORS["pin"], stroke_width=1.5))
                g.add(dwg.circle(center=(pin.x, pin.y), r=2.5, fill=SCH_COLORS["pin"]))
            elif pin.side == "bottom":
                g.add(dwg.line(start=(pin.x, y + h), end=(pin.x, pin.y),
                               stroke=SCH_COLORS["pin"], stroke_width=1.5))
                g.add(dwg.circle(center=(pin.x, pin.y), r=2.5, fill=SCH_COLORS["pin"]))

        return g

    def _draw_resistor(self, dwg, g, x, cy, w):
        """IEEE resistor zigzag symbol."""
        # Lead-in line from left edge to zigzag start
        zag_start = x + 10
        zag_end = x + w - 10
        zag_w = zag_end - zag_start
        teeth = 6
        tooth_w = zag_w / teeth
        amplitude = 8

        # Left lead
        g.add(dwg.line(start=(x, cy), end=(zag_start, cy),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Right lead
        g.add(dwg.line(start=(zag_end, cy), end=(x + w, cy),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))

        # Zigzag
        points = [(zag_start, cy)]
        for i in range(teeth):
            tx = zag_start + (i + 0.25) * tooth_w
            points.append((tx, cy - amplitude))
            tx = zag_start + (i + 0.75) * tooth_w
            points.append((tx, cy + amplitude))
        points.append((zag_end, cy))
        g.add(dwg.polyline(points=points, fill="none",
                           stroke=SCH_COLORS["component"], stroke_width=1.5))

    def _draw_wiper_arrow(self, dwg, g, cx, cy):
        """Arrow for potentiometer wiper — points up to the body."""
        # Arrow line from below
        g.add(dwg.line(start=(cx, cy + 20), end=(cx, cy + 4),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Arrowhead
        g.add(dwg.polygon(
            points=[(cx, cy + 2), (cx - 4, cy + 10), (cx + 4, cy + 10)],
            fill=SCH_COLORS["component"]
        ))

    def _draw_capacitor(self, dwg, g, x, cy, w):
        """Capacitor symbol — two parallel plates."""
        plate_x = x + w // 2
        plate_gap = 6
        plate_h = 20
        # Left lead
        g.add(dwg.line(start=(x, cy), end=(plate_x - plate_gap, cy),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Right lead
        g.add(dwg.line(start=(plate_x + plate_gap, cy), end=(x + w, cy),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Left plate
        g.add(dwg.line(start=(plate_x - plate_gap, cy - plate_h // 2),
                       end=(plate_x - plate_gap, cy + plate_h // 2),
                       stroke=SCH_COLORS["component"], stroke_width=2.5))
        # Right plate
        g.add(dwg.line(start=(plate_x + plate_gap, cy - plate_h // 2),
                       end=(plate_x + plate_gap, cy + plate_h // 2),
                       stroke=SCH_COLORS["component"], stroke_width=2.5))

    def _draw_switch(self, dwg, g, x, cy, w):
        """Simple SPST switch symbol."""
        # Left terminal dot
        g.add(dwg.circle(center=(x + 15, cy), r=3,
                         fill="none", stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Right terminal dot
        g.add(dwg.circle(center=(x + w - 15, cy), r=3,
                         fill="none", stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Lever (angled line from left dot toward right dot, not touching)
        g.add(dwg.line(start=(x + 18, cy), end=(x + w - 20, cy - 12),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Lead lines
        g.add(dwg.line(start=(x, cy), end=(x + 12, cy),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))
        g.add(dwg.line(start=(x + w - 12, cy), end=(x + w, cy),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))

    def _draw_buzzer_symbol(self, dwg, g, x, y, w, h):
        """Buzzer/speaker schematic symbol."""
        cy = y + h // 2
        # Left lead
        g.add(dwg.line(start=(x, cy), end=(x + 15, cy),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Small rectangle (transducer)
        g.add(dwg.rect(insert=(x + 15, y + 2), size=(20, h - 4),
                       fill=SCH_COLORS["fill"],
                       stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Horn shape (trapezoid expanding right)
        horn_pts = [
            (x + 35, y + 5),
            (x + w - 10, y - 5),
            (x + w - 10, y + h + 5),
            (x + 35, y + h - 5)
        ]
        g.add(dwg.polygon(points=horn_pts,
                          fill=SCH_COLORS["fill"],
                          stroke=SCH_COLORS["component"], stroke_width=1.5))
        # Right lead
        g.add(dwg.line(start=(x + w - 10, cy), end=(x + w, cy),
                       stroke=SCH_COLORS["component"], stroke_width=1.5))


class LEDMatrixSymbol(SchematicSymbol):
    """LED matrix module — drawn as a labeled box with pin array."""

    def __init__(self, comp_id: str, ref_des: str, x: float, y: float,
                 value: str = "MAX7219"):
        super().__init__(comp_id, ref_des, x, y)
        self.value = value
        self.width = 120
        # 5 pins on the left side
        pin_list = [("VCC", "power"), ("GND", "ground"),
                    ("DIN", "input"), ("CS", "input"), ("CLK", "input")]
        self.height = len(pin_list) * PIN_SPACING + COMP_PADDING * 2

        for i, (name, ptype) in enumerate(pin_list):
            py = y + COMP_PADDING + i * PIN_SPACING + PIN_SPACING // 2
            px = x - PIN_LENGTH
            self.pins[name] = SchPin(name, px, py, "left", ptype)

    def render(self, dwg: svgwrite.Drawing) -> svgwrite.container.Group:
        g = dwg.g(id=f"sch_{self.id}")
        x, y, w, h = self.x, self.y, self.width, self.height

        # Body
        g.add(dwg.rect(insert=(x, y), size=(w, h),
                       fill=SCH_COLORS["fill"],
                       stroke=SCH_COLORS["component"], stroke_width=2))

        # Ref des
        g.add(dwg.text(self.ref_des, insert=(x + w / 2, y - 8),
                       fill=SCH_COLORS["refdes"], font_size="12px",
                       font_family="monospace", font_weight="bold",
                       text_anchor="middle"))

        # Value
        g.add(dwg.text(self.value, insert=(x + w / 2, y + h + 16),
                       fill=SCH_COLORS["value"], font_size="10px",
                       font_family="monospace", text_anchor="middle"))

        # 8x8 dot grid inside (representing the LED matrix)
        grid_size = min(w, h) - 30
        gx_start = x + w / 2 - grid_size / 3
        gy_start = y + COMP_PADDING
        dot_spacing = grid_size / 10
        for row in range(8):
            for col in range(8):
                dx = gx_start + col * dot_spacing
                dy = gy_start + row * dot_spacing
                g.add(dwg.circle(center=(dx, dy), r=1.5,
                                 fill="#cc0000", opacity=0.4))

        # Pin stubs and labels
        for name, pin in self.pins.items():
            g.add(dwg.line(start=(pin.x, pin.y), end=(x, pin.y),
                           stroke=SCH_COLORS["pin"], stroke_width=1.5))
            g.add(dwg.circle(center=(pin.x, pin.y), r=2.5,
                             fill=SCH_COLORS["pin"]))
            g.add(dwg.text(name, insert=(x + 6, pin.y + 4),
                           fill=SCH_COLORS["pin_label"], font_size="9px",
                           font_family="monospace"))

        return g


# ─── Power Symbols ───────────────────────────────────────────────

def draw_vcc_symbol(dwg: svgwrite.Drawing, x: float, y: float,
                     label: str = "VCC") -> svgwrite.container.Group:
    """Standard VCC power symbol — upward arrow/bar."""
    g = dwg.g()
    # Vertical line
    g.add(dwg.line(start=(x, y), end=(x, y - 15),
                   stroke=SCH_COLORS["power_wire"], stroke_width=1.5))
    # Horizontal bar at top
    g.add(dwg.line(start=(x - 10, y - 15), end=(x + 10, y - 15),
                   stroke=SCH_COLORS["power_wire"], stroke_width=2))
    # Label
    g.add(dwg.text(label, insert=(x, y - 20),
                   fill=SCH_COLORS["power_wire"], font_size="9px",
                   font_family="monospace", font_weight="bold",
                   text_anchor="middle"))
    return g


def draw_gnd_symbol(dwg: svgwrite.Drawing, x: float, y: float) -> svgwrite.container.Group:
    """Standard ground symbol — three horizontal lines of decreasing width."""
    g = dwg.g()
    # Vertical line
    g.add(dwg.line(start=(x, y), end=(x, y + 10),
                   stroke=SCH_COLORS["ground_wire"], stroke_width=1.5))
    # Three bars
    for i, hw in enumerate([10, 7, 4]):
        bar_y = y + 10 + i * 4
        g.add(dwg.line(start=(x - hw, bar_y), end=(x + hw, bar_y),
                       stroke=SCH_COLORS["ground_wire"], stroke_width=1.5))
    return g


# ─── Net / Wire rendering for schematic mode ─────────────────────

def render_schematic_wires(dwg: svgwrite.Drawing,
                           connections: List[dict],
                           symbols: Dict[str, SchematicSymbol]) -> svgwrite.container.Group:
    """
    Render schematic connections as simple orthogonal net lines.
    In schematic mode, wires are straight L-shaped lines (one bend max)
    with net labels, not routed around obstacles.
    """
    g = dwg.g(id="nets")

    for conn in connections:
        from_parts = conn["from"].split(":", 1)
        to_parts = conn["to"].split(":", 1)

        if len(from_parts) != 2 or len(to_parts) != 2:
            continue

        from_id, from_pin = from_parts
        to_id, to_pin = to_parts

        if from_id not in symbols or to_id not in symbols:
            print(f"WARNING: Schematic symbol not found for {from_id} or {to_id}")
            continue

        try:
            sx, sy = symbols[from_id].get_pin(from_pin)
            ex, ey = symbols[to_id].get_pin(to_pin)
        except ValueError as e:
            print(f"WARNING: {e}")
            continue

        # Determine wire color based on pin type
        wire_color = SCH_COLORS["wire"]
        if from_pin in ("VCC", "5V", "3.3V", "+") or to_pin in ("VCC", "5V", "3.3V", "+"):
            wire_color = SCH_COLORS["power_wire"]
        elif from_pin.startswith("GND") or to_pin.startswith("GND") or from_pin == "-" or to_pin == "-":
            wire_color = SCH_COLORS["ground_wire"]

        # Simple L-shaped route: horizontal then vertical
        mid_x = ex
        mid_y = sy

        # Draw the two segments
        g.add(dwg.line(start=(sx, sy), end=(mid_x, mid_y),
                       stroke=wire_color, stroke_width=1.5))
        g.add(dwg.line(start=(mid_x, mid_y), end=(ex, ey),
                       stroke=wire_color, stroke_width=1.5))

        # Junction dot at the bend
        if abs(sx - ex) > 5 and abs(sy - ey) > 5:
            g.add(dwg.circle(center=(mid_x, mid_y), r=2.5,
                             fill=wire_color))

        # Net label (if specified)
        label = conn.get("label")
        if label:
            lx = (sx + ex) / 2
            ly = (sy + ey) / 2 - 6
            g.add(dwg.text(label, insert=(lx, ly),
                           fill=SCH_COLORS["net_label"],
                           font_size="8px", font_family="monospace",
                           font_weight="bold", text_anchor="middle"))

    return g


# ─── Schematic symbol factory ────────────────────────────────────
# Maps component types to schematic symbol generators

def create_schematic_symbol(comp_type: str, comp_id: str,
                             x: float, y: float,
                             attrs: dict = None) -> SchematicSymbol:
    """
    Factory function: given a component type from the JSON config,
    create the appropriate schematic symbol. Auto-assigns reference
    designators based on type.
    """
    attrs = attrs or {}

    if comp_type == "arduino-uno":
        return MCUSymbol(
            comp_id, "U1", x, y,
            left_pins=[
                ("A0", "input"), ("A1", "input"), ("A2", "input"),
                ("A3", "input"), ("A4", "input"), ("A5", "input"),
                ("VIN", "power"), ("GND.1", "ground"), ("GND.3", "ground"),
                ("5V", "power"), ("3.3V", "power"), ("RESET", "input"),
            ],
            right_pins=[
                ("SCL", "bidirectional"), ("SDA", "bidirectional"),
                ("AREF", "input"), ("GND.2", "ground"),
                ("13", "bidirectional"), ("12", "bidirectional"),
                ("11", "bidirectional"), ("10", "bidirectional"),
                ("9", "bidirectional"), ("8", "bidirectional"),
                ("7", "bidirectional"), ("6", "bidirectional"),
                ("5", "bidirectional"), ("4", "bidirectional"),
                ("3", "bidirectional"), ("2", "bidirectional"),
                ("1", "bidirectional"), ("0", "bidirectional"),
                ("USB", "bidirectional"),
            ],
            value="ATmega328P"
        )

    elif comp_type == "raspberry-pi":
        return MCUSymbol(
            comp_id, "SBC1", x, y,
            left_pins=[
                ("USB1", "bidirectional"),
                ("USB2", "bidirectional"),
                ("USB3", "bidirectional"),
                ("USB4", "bidirectional"),
            ],
            right_pins=[
                ("GPIO_1", "bidirectional"),
                ("GPIO_2", "bidirectional"),
                ("GPIO_3", "bidirectional"),
                ("GPIO_4", "bidirectional"),
            ],
            value="Raspberry Pi"
        )

    elif comp_type == "max7219-matrix":
        return LEDMatrixSymbol(comp_id, "LED1", x, y, value="MAX7219 8x8")

    elif comp_type == "potentiometer":
        return PassiveSymbol(
            comp_id, "RV1", x, y,
            symbol_type="potentiometer", value="10K",
            pin_names=("1", "3"), extra_pin="2"
        )

    elif comp_type == "pushbutton":
        return PassiveSymbol(
            comp_id, "SW1", x, y,
            symbol_type="switch", value="",
            pin_names=("1.1", "2.1")
        )

    elif comp_type == "piezo-buzzer":
        return PassiveSymbol(
            comp_id, "BZ1", x, y,
            symbol_type="buzzer", value="Piezo",
            pin_names=("1", "2")
        )

    elif comp_type == "battery-9v":
        return PassiveSymbol(
            comp_id, "BT1", x, y,
            symbol_type="capacitor", value="9V",
            pin_names=("+", "-")
        )

    elif comp_type == "breadboard":
        # Breadboards don't appear in schematics — they're physical only.
        # We create a transparent passthrough that maps power rail pins
        # to VCC/GND symbols instead.
        return None

    else:
        # Generic box symbol
        return MCUSymbol(
            comp_id, "X1", x, y,
            left_pins=[("IN", "input")],
            right_pins=[("OUT", "output")],
            value=comp_type
        )


def generate_schematic(config: dict, output_path: str,
                        png: bool = False, scale: float = 2.0):
    """
    Generate a schematic diagram from the same JSON config
    used for breadboard diagrams.

    Key difference: breadboards are eliminated. Components that
    connect to breadboard power rails connect to VCC/GND symbols
    instead. Layout is auto-placed in a logical arrangement.
    """
    print(f"[SCH] Generating schematic...")

    parts = config["parts"]
    connections = config["connections"]

    # ── Create schematic symbols ──
    symbols: Dict[str, SchematicSymbol] = {}
    ref_counters = {}  # for auto-incrementing ref des

    # Auto-layout: place components in a grid
    col_x = [80, 400, 700]  # three columns
    row_y = 60
    col_idx = 0

    for part in parts:
        comp_type = part["type"]
        comp_id = part["id"]
        attrs = part.get("attrs", {})

        sym = create_schematic_symbol(comp_type, comp_id,
                                       col_x[col_idx % len(col_x)], row_y, attrs)

        if sym is None:
            # Breadboard — skip in schematic mode
            continue

        symbols[comp_id] = sym
        row_y += sym.height + 80  # vertical spacing between symbols

        # Wrap to next column if we've gone too far down
        if row_y > 700:
            row_y = 60
            col_idx += 1

    # ── Compute canvas ──
    max_x = max_y = 0
    for sym in symbols.values():
        right = sym.x + sym.width + PIN_LENGTH + 60
        bottom = sym.y + sym.height + 60
        max_x = max(max_x, right)
        max_y = max(max_y, bottom)

    canvas_w = int(max_x + 80)
    canvas_h = int(max_y + 80)

    # ── Create SVG ──
    dwg = svgwrite.Drawing(output_path,
                            size=(f"{canvas_w}px", f"{canvas_h}px"),
                            viewBox=f"0 0 {canvas_w} {canvas_h}")

    # White background
    dwg.add(dwg.rect(insert=(0, 0), size=(canvas_w, canvas_h),
                      fill=SCH_COLORS["bg"]))

    # Grid dots
    for gx in range(0, canvas_w, GRID):
        for gy in range(0, canvas_h, GRID):
            dwg.add(dwg.circle(center=(gx, gy), r=0.3,
                               fill=SCH_COLORS["grid"]))

    # ── Render symbols ──
    for sym in symbols.values():
        dwg.add(sym.render(dwg))

    # ── Remap breadboard connections ──
    # In schematic mode, "bb:tp.N" (power rail) connections go to
    # a VCC symbol, and "bb:tn.N" (ground rail) connections go to
    # a GND symbol. We filter these out and add power symbols.
    remapped = []
    power_points = []  # (x, y) where VCC symbols should appear
    gnd_points = []    # (x, y) where GND symbols should appear

    for conn in connections:
        from_str = conn["from"]
        to_str = conn["to"]

        # Check if either side references a breadboard power rail
        from_is_bb_power = "bb:tp." in from_str or "bb:bp." in from_str
        from_is_bb_gnd = "bb:tn." in from_str or "bb:bn." in from_str
        to_is_bb_power = "bb:tp." in to_str or "bb:bp." in to_str
        to_is_bb_gnd = "bb:tn." in to_str or "bb:bn." in to_str

        if from_is_bb_power or from_is_bb_gnd or to_is_bb_power or to_is_bb_gnd:
            # This wire connects something to a power/ground rail.
            # In schematic mode, add a VCC/GND symbol at the component's pin.
            non_bb_side = from_str if (to_is_bb_power or to_is_bb_gnd) else to_str
            is_power = from_is_bb_power or to_is_bb_power

            parts_split = non_bb_side.split(":", 1)
            if len(parts_split) == 2 and parts_split[0] in symbols:
                try:
                    px, py = symbols[parts_split[0]].get_pin(parts_split[1])
                    if is_power:
                        power_points.append((px, py))
                    else:
                        gnd_points.append((px, py))
                except ValueError:
                    pass
            continue

        # Skip any connection where either side is a breadboard grid hole
        from_id = from_str.split(":")[0]
        to_id = to_str.split(":")[0]
        if from_id == "bb" or to_id == "bb":
            continue

        remapped.append(conn)

    # Draw VCC/GND symbols
    for px, py in power_points:
        dwg.add(draw_vcc_symbol(dwg, px, py))
    for px, py in gnd_points:
        dwg.add(draw_gnd_symbol(dwg, px, py))

    # ── Render net wires ──
    wire_group = render_schematic_wires(dwg, remapped, symbols)
    dwg.add(wire_group)

    # ── Title block ──
    title = config.get("title", "")
    if title:
        dwg.add(dwg.text(f"SCHEMATIC: {title}",
                          insert=(40, canvas_h - 20),
                          fill=SCH_COLORS["title"], font_size="14px",
                          font_family="monospace", font_weight="bold"))

    # ── Border ──
    dwg.add(dwg.rect(insert=(2, 2), size=(canvas_w - 4, canvas_h - 4),
                      fill="none", stroke=SCH_COLORS["border"], stroke_width=1.5))

    dwg.save()
    print(f"[SCH] Saved: {output_path}")

    if png:
        try:
            import cairosvg
            png_path = output_path.rsplit('.', 1)[0] + '.png'
            with open(output_path, 'r') as f:
                svg_data = f.read()
            cairosvg.svg2png(bytestring=svg_data.encode('utf-8'),
                             write_to=png_path, scale=scale)
            print(f"[SCH] Saved: {png_path}")
        except ImportError:
            print("[SCH] WARNING: cairosvg not available for PNG conversion")

    print("[SCH] Done!")
