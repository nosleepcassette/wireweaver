# HANDOVER: Breadboard-as-Code Diagram Generator

## Date: 2026-03-25
## Agent: cassette (Claude Opus 4.6)
## Status: MVP Complete — Functional, Needs Polish

---

## What Was Built

A Python CLI tool (`breadboard_diagram.py`) that generates Fritzing-style electronic breadboard wiring diagrams from declarative JSON configuration files. Zero AI hallucinations — every pin coordinate is exact, every wire is routed programmatically.

### Architecture (3 modules, ~1600 LOC)

```
breadboard_diagram.py  — CLI entry point, config parser, SVG compositor
components.py          — Procedural SVG component library (8 components)
router.py              — A* orthogonal wire routing engine with collision avoidance
```

### Component Library

| Component | Type Key | Pins Exposed |
|---|---|---|
| Arduino Uno R3 | `arduino-uno` | D0-D13, A0-A5, 5V, 3.3V, GND, VIN, RESET, USB, SCL, SDA, AREF |
| Breadboard (half) | `breadboard` | tp.1-30, tn.1-30 (rails), a1-j30 (grid) |
| MAX7219 8x8 Matrix | `max7219-matrix` | VCC, GND, DIN, CS, CLK |
| Potentiometer 10K | `potentiometer` | 1 (VCC), 2 (wiper), 3 (GND) |
| Push Button | `pushbutton` | 1.1, 1.2, 2.1, 2.2 (4-pin) |
| Piezo Buzzer | `piezo-buzzer` | 1 (-), 2 (+) |
| 9V Battery | `battery-9v` | +, - |
| Raspberry Pi | `raspberry-pi` | USB1-4, GPIO_1-20 |

### Wire Router

- Grid-based A* pathfinding (4px cells)
- Orthogonal-only paths (no diagonals)
- Collision avoidance: occupied cells blocked, adjacent cells penalized
- Auto color-coding by pin function (power=red, ground=black, data=blue, clock=green, etc.)
- Wire termination dots at both endpoints
- Optional per-wire labels

### JSON Config Format

```json
{
    "title": "My Circuit",
    "description": "Optional subtitle",
    "parts": [
        {"type": "arduino-uno", "id": "uno", "x": 300, "y": 60},
        {"type": "breadboard", "id": "bb", "x": 140, "y": 520}
    ],
    "connections": [
        {"from": "uno:5V", "to": "bb:tp.1", "label": "+5V"},
        {"from": "uno:GND.1", "to": "bb:tn.1", "color": "#222222"}
    ]
}
```

---

## What Works

- [x] Config parsing (JSON)
- [x] All 8 component types render with procedural SVG
- [x] Wire routing with A* pathfinding and collision avoidance
- [x] Auto color-coding by wire category
- [x] Wire termination dots
- [x] Wire labels
- [x] Color legend
- [x] Title block
- [x] SVG output
- [x] PNG conversion (via cairosvg)
- [x] CLI with argparse

## What Needs Work (Next Session)

### High Priority
- **Wire routing quality**: SPI wires (multiple wires between physically close pins) still cluster. Need to implement channel-based routing or post-route nudging for parallel wire bundles
- **Component-to-breadboard alignment**: Components above the breadboard (pot, button, buzzer) should snap their pins to actual breadboard holes rather than floating
- **Arduino pin spacing accuracy**: Current spacing is approximate. Real Uno has 0.1" (2.54mm) pin pitch — needs calibration against actual board dimensions

### Medium Priority
- **SVG component library export**: Each component should be exportable as a standalone SVG for Atlas's repo-wide library
- **Schematic mode**: Dual-representation architecture is in place (base `Component` class). Need to add schematic symbol rendering to each component class and a `"mode": "schematic"` flag in the JSON config
- **Auto-layout engine**: Currently positions are manual (x/y in JSON). Could add an auto-placement mode that arranges components optimally
- **Wire routing visual options**: Curved wires, bundled bus lines, junction dots where wires cross power rails

### Low Priority  
- **YAML support**: Config parser only does JSON currently
- **Interactive SVG**: Could add hover tooltips showing pin names and connection info
- **BOM generation**: Parts list / bill of materials from the config
- **Validation**: Check for short circuits, missing connections, pin conflicts

---

## How to Extend

### Adding a new component

1. Create a new class in `components.py` inheriting from `Component`
2. Set `W` and `H` class attributes
3. Implement `_compute_pins()` to define pin names → (x,y) coordinates
4. Implement `render()` to draw the SVG using `svgwrite`
5. Register in `COMPONENT_REGISTRY` dict at bottom of file

### Adding schematic symbols (future)

Each component class should add a `render_schematic()` method returning a simplified symbol SVG. The main script checks `config["mode"]` to choose which renderer to call.

---

## Dependencies

```
svgwrite    — SVG generation
cairosvg    — SVG → PNG conversion (optional)
```

## Usage

```bash
python breadboard_diagram.py diagram.json                    # SVG only
python breadboard_diagram.py diagram.json --png              # SVG + PNG
python breadboard_diagram.py diagram.json -o custom.svg      # custom output path
python breadboard_diagram.py diagram.json --png --scale 3.0  # high-res PNG
```

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-03-25 | Initial MVP: 8 components, A* router, SVG+PNG output |
| v0.1.1 | 2026-03-25 | Fix matrix pin label overlap (angled labels) |
| v0.1.2 | 2026-03-25 | Fix Arduino pin labels (inside board like silkscreen) |
| v0.1.3 | 2026-03-25 | Increase wire spacing penalty (8→ from 3), finer grid (4px) |
| v0.1.4 | 2026-03-25 | Layout tuning: spread components, move legend to bottom-right |
