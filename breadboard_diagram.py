#!/usr/bin/env python3
"""
breadboard_diagram.py — Breadboard-as-Code Diagram Generator
=============================================================
A command-line tool that programmatically generates Fritzing-style
electronic breadboard wiring diagrams from declarative JSON configs.

Usage:
    python breadboard_diagram.py diagram.json [-o output.svg] [--png]

The JSON config specifies:
    - "parts": array of component definitions (type, id, position)
    - "connections": array of wire definitions (from, to, color, label)

Output: A single, clean, scalable SVG file (and optionally PNG).
"""

import json
import sys
import os
import argparse
from typing import Dict, List, Any

import svgwrite
try:
    import cairosvg
    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False

from components import (
    Component, COMPONENT_REGISTRY, COLORS,
    ArduinoUno, Breadboard, MAX7219Matrix,
    Potentiometer, PushButton, PiezoBuzzer,
    Battery9V, RaspberryPi
)
from router import Wire, WireRouter, render_wires, detect_wire_category


CANVAS_PADDING = 40
BG_COLOR = "#f8f6f0"
GRID_DOT_COLOR = "#e0ddd5"


def parse_config(config_path: str) -> dict:
    """Parse a diagram JSON configuration file."""
    with open(config_path, 'r') as f:
        config = json.load(f)
    if "parts" not in config:
        raise ValueError("Config must contain a 'parts' array")
    if "connections" not in config:
        raise ValueError("Config must contain a 'connections' array")
    return config


def create_components(parts_config: List[dict]) -> Dict[str, Component]:
    """Instantiate Component objects from config parts array."""
    components = {}
    for part in parts_config:
        comp_type = part["type"]
        comp_id = part["id"]
        x = part.get("x", 0)
        y = part.get("y", 0)
        attrs = part.get("attrs", {})

        if comp_type not in COMPONENT_REGISTRY:
            print(f"WARNING: Unknown component type '{comp_type}', skipping. "
                  f"Available: {', '.join(COMPONENT_REGISTRY.keys())}")
            continue

        cls = COMPONENT_REGISTRY[comp_type]

        if comp_type == "max7219-matrix":
            components[comp_id] = cls(comp_id, x, y, color=attrs.get("color", "red"))
        elif comp_type == "pushbutton":
            components[comp_id] = cls(comp_id, x, y, color=attrs.get("color", "red"))
        else:
            components[comp_id] = cls(comp_id, x, y)

    return components


def parse_connections(conn_config: List[dict]) -> List[Wire]:
    """Parse connection definitions into Wire objects."""
    wires = []
    for conn in conn_config:
        from_parts = conn["from"].split(":", 1)
        to_parts = conn["to"].split(":", 1)
        if len(from_parts) != 2 or len(to_parts) != 2:
            print(f"WARNING: Invalid connection format: {conn}")
            continue
        wire = Wire(
            from_comp=from_parts[0],
            from_pin=from_parts[1],
            to_comp=to_parts[0],
            to_pin=to_parts[1],
            color=conn.get("color"),
            label=conn.get("label"),
        )
        wire.category = detect_wire_category(wire.from_pin, wire.to_pin)
        wires.append(wire)
    return wires


def compute_canvas_size(components: Dict[str, Component]) -> tuple:
    """Calculate required canvas dimensions from component bounds."""
    if not components:
        return (800, 600)
    max_x = max_y = 0
    for comp in components.values():
        max_x = max(max_x, comp.x + comp.width)
        max_y = max(max_y, comp.y + comp.height)
    return (int(max_x + CANVAS_PADDING * 3), int(max_y + CANVAS_PADDING * 3))


def add_background(dwg, w, h):
    """Render background with subtle dot grid."""
    dwg.add(dwg.rect(insert=(0, 0), size=(w, h), fill=BG_COLOR))
    for gx in range(0, w, 20):
        for gy in range(0, h, 20):
            dwg.add(dwg.circle(center=(gx, gy), r=0.4, fill=GRID_DOT_COLOR))


def add_title_block(dwg, config, w, h):
    """Add title and description if present."""
    title = config.get("title", "")
    desc = config.get("description", "")
    if title:
        dwg.add(dwg.text(title, insert=(CANVAS_PADDING, h - 20),
                          fill=COLORS["label_dark"], font_size="14px",
                          font_family="monospace", font_weight="bold", opacity=0.6))
    if desc:
        dwg.add(dwg.text(desc, insert=(CANVAS_PADDING, h - 6),
                          fill=COLORS["label_dim"], font_size="9px",
                          font_family="monospace", opacity=0.5))


def add_legend(dwg, wires, x, y):
    """Add wire color legend for categories used in the diagram."""
    from router import WIRE_COLORS
    categories = set(w.category for w in wires)
    if not categories:
        return

    g = dwg.g(id="legend")
    legend_h = len(categories) * 16 + 24
    g.add(dwg.rect(insert=(x, y), size=(120, legend_h), rx=4,
                    fill="#ffffff", stroke="#ddd", stroke_width=0.5, opacity=0.9))
    g.add(dwg.text("WIRE LEGEND", insert=(x + 8, y + 14),
                    fill=COLORS["label_dark"], font_size="7px",
                    font_family="monospace", font_weight="bold"))

    for i, cat in enumerate(sorted(categories)):
        ey = y + 28 + i * 16
        color = WIRE_COLORS.get(cat, "#888")
        g.add(dwg.line(start=(x + 8, ey), end=(x + 28, ey),
                        stroke=color, stroke_width=2.5, stroke_linecap="round"))
        g.add(dwg.circle(center=(x + 8, ey), r=2.5, fill=color))
        g.add(dwg.circle(center=(x + 28, ey), r=2.5, fill=color))
        g.add(dwg.text(cat.upper(), insert=(x + 36, ey + 3),
                        fill=COLORS["label_dark"], font_size="7px", font_family="monospace"))
    dwg.add(g)


def generate_diagram(config_path, output_path, png=False, scale=2.0):
    """Main generation pipeline."""
    print(f"[1/6] Parsing config: {config_path}")
    config = parse_config(config_path)

    print(f"[2/6] Creating {len(config['parts'])} components...")
    components = create_components(config["parts"])
    print(f"       Loaded: {', '.join(components.keys())}")

    print(f"[3/6] Computing canvas layout...")
    canvas_w, canvas_h = compute_canvas_size(components)
    print(f"       Canvas: {canvas_w} x {canvas_h} px")

    print(f"[4/6] Initializing wire router...")
    router = WireRouter(canvas_w, canvas_h)
    for comp in components.values():
        router.add_blocked_zone(comp.x, comp.y,
                                 comp.x + comp.width, comp.y + comp.height, margin=1)

    print(f"[5/6] Rendering SVG...")
    dwg = svgwrite.Drawing(output_path, size=(f"{canvas_w}px", f"{canvas_h}px"),
                            viewBox=f"0 0 {canvas_w} {canvas_h}")

    add_background(dwg, canvas_w, canvas_h)

    # Render components (behind wires)
    for comp in components.values():
        dwg.add(comp.render(dwg))

    # Parse and route wires
    wires = parse_connections(config["connections"])
    print(f"       Routing {len(wires)} wires...")
    wire_group = render_wires(dwg, wires, components, router)
    dwg.add(wire_group)

    add_title_block(dwg, config, canvas_w, canvas_h)
    add_legend(dwg, wires, canvas_w - 140, canvas_h - 180)

    dwg.save()
    print(f"       Saved: {output_path}")

    if png:
        print(f"[6/6] Converting to PNG...")
        if not HAS_CAIRO:
            print("       WARNING: cairosvg not installed, skipping PNG")
        else:
            png_path = output_path.rsplit('.', 1)[0] + '.png'
            with open(output_path, 'r') as f:
                svg_content = f.read()
            cairosvg.svg2png(bytestring=svg_content.encode('utf-8'),
                             write_to=png_path, scale=scale)
            print(f"       Saved: {png_path}")

    print("\nDone! Diagram generated successfully.")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Breadboard-as-Code: Generate wiring diagrams from JSON configs")
    parser.add_argument("config", help="Path to diagram JSON config file")
    parser.add_argument("-o", "--output", default=None, help="Output SVG path")
    parser.add_argument("--png", action="store_true", help="Also generate PNG")
    parser.add_argument("--scale", type=float, default=2.0, help="PNG scale factor")
    parser.add_argument("--mode", choices=["breadboard", "schematic"], default="breadboard",
                        help="Rendering mode: 'breadboard' (physical layout) or 'schematic' (logical connections)")
    args = parser.parse_args()

    if args.output is None:
        base = os.path.splitext(os.path.basename(args.config))[0]
        suffix = "_schematic" if args.mode == "schematic" else "_diagram"
        args.output = f"{base}{suffix}.svg"

    if args.mode == "schematic":
        # Use the schematic renderer
        from schematic import generate_schematic
        config = parse_config(args.config)
        generate_schematic(config, args.output, png=args.png, scale=args.scale)
    else:
        generate_diagram(args.config, args.output, png=args.png, scale=args.scale)


if __name__ == "__main__":
    main()
