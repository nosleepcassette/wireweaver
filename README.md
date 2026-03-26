# WireWeaver

**Breadboard-as-Code: Programmatic Electronic Diagram Generator**

A Python CLI tool that generates Fritzing-style breadboard wiring diagrams AND IEEE-style schematic diagrams from declarative JSON configuration files. Zero AI hallucinations — every pin coordinate is exact, every wire is routed programmatically.

![breadboard diagram](/example/img/tamagotchi_diagram.png)
![schematic diagram](/example/img/tamagotchi_diagram_schematic.png)
## Why?

I needed to programatically make Fritzing-style breadboard wiring diagrams for a deranged art project, and while there were great CLI schematic diagram generators, there wasn't one for breadboarding, and other programs required creating heavy & highly specialized XML files.

- **Components** are drawn procedurally with exact pin coordinates
- **Wires** are routed via A* pathfinding with collision avoidance  
- **Schematics** use standard IEEE symbols with proper net labels
- **Output** is clean, scalable SVG (with optional PNG conversion)

The same JSON config generates both views — physical (breadboard) and logical (schematic).

## Quick Start

```bash
# Install dependencies
pip install svgwrite cairosvg

# Generate a breadboard diagram
python breadboard_diagram.py tamagotchi_diagram.json --png

# Generate a schematic from the same config
python breadboard_diagram.py tamagotchi_diagram.json --mode schematic --png

# Custom output path and scale
python breadboard_diagram.py my_circuit.json -o my_output.svg --png --scale 3.0
```

## JSON Config Format

```json
{
    "title": "My Circuit",
    "description": "Optional subtitle text",
    
    "parts": [
        {"type": "arduino-uno", "id": "uno", "x": 300, "y": 60},
        {"type": "breadboard", "id": "bb", "x": 140, "y": 520},
        {"type": "max7219-matrix", "id": "matrix", "x": 600, "y": 120, 
         "attrs": {"color": "red"}},
        {"type": "potentiometer", "id": "pot", "x": 170, "y": 430},
        {"type": "pushbutton", "id": "btn", "x": 270, "y": 438,
         "attrs": {"color": "green"}},
        {"type": "piezo-buzzer", "id": "buzzer", "x": 360, "y": 420}
    ],
    
    "connections": [
        {"from": "uno:5V", "to": "bb:tp.1", "label": "+5V"},
        {"from": "uno:GND.1", "to": "bb:tn.1"},
        {"from": "matrix:DIN", "to": "uno:11", "label": "MOSI"},
        {"from": "pot:2", "to": "uno:A0", "label": "WIPER"}
    ]
}
```

### Parts

The `"parts"` array defines components. Each part needs:

| Field    | Required | Description                                                                |
|----------|----------|----------------------------------------------------------------------------|
| `type`   | Yes      | Component type (see table below)                                           |
| `id`     | Yes      | Unique identifier for wiring references                                    |
| `x`, `y` | Yes*     | Position on canvas (*breadboard mode only; auto-placed in schematic mode*) |
| `attrs`  | No       | Component-specific attributes (e.g., `{"color": "green"}`)                 |

### Supported Component Types

| Type Key | Component | Breadboard | Schematic | Notes |
|---|---|---|---|---|
| `arduino-uno` | Arduino Uno R3 | Full PCB render | MCU rectangle (U1) | D0-D13, A0-A5, power pins |
| `raspberry-pi` | Raspberry Pi 3/4 | Full PCB render | SBC rectangle | USB1-4, GPIO_1-20 |
| `breadboard` | Half-size breadboard | 30-col grid | *Omitted* | tp/tn/bp/bn rails, a1-j30 grid |
| `max7219-matrix` | 8x8 LED Matrix | Module render | LED symbol | VCC, GND, DIN, CS, CLK |
| `potentiometer` | 10K Rotary Pot | Knob render | Zigzag + arrow | Pins: 1 (VCC), 2 (wiper), 3 (GND) |
| `pushbutton` | Tactile Button | Cap render | SPST switch | Pins: 1.1, 1.2, 2.1, 2.2 |
| `piezo-buzzer` | Piezo Buzzer | Disc render | Speaker symbol | Pins: 1 (-), 2 (+) |
| `battery-9v` | 9V Battery | Battery render | *Generic* | Pins: +, - |

### Connections

The `"connections"` array defines wires. Format: `"component_id:pin_name"`.

| Field | Required | Description |
|---|---|---|
| `from` | Yes | Source: `"comp_id:pin_name"` |
| `to` | Yes | Destination: `"comp_id:pin_name"` |
| `color` | No | Override wire color (hex, e.g., `"#cc2222"`) |
| `label` | No | Wire label text (e.g., `"MOSI"`, `"+5V"`) |

### Auto Color Coding

Wires are automatically color-coded by function when no explicit color is set:

| Category | Color | Triggered By |
|---|---|---|
| Power | Red | VCC, 5V, 3.3V, + pins |
| Ground | Black | GND, - pins |
| Data | Blue | DIN, MOSI, MISO, SDA |
| Clock | Green | CLK, SCK, SCL |
| Chip Select | Yellow | CS, SS |
| Analog | Purple | A0-A5 |
| Digital | Orange | All other digital pins |

### Breadboard Pin Names

The breadboard component uses this naming convention:

| Pin Pattern | Meaning | Example |
|---|---|---|
| `tp.N` | Top positive rail, column N | `bb:tp.1` |
| `tn.N` | Top negative rail, column N | `bb:tn.5` |
| `bp.N` | Bottom positive rail | `bb:bp.10` |
| `bn.N` | Bottom negative rail | `bb:bn.15` |
| `[a-j]N` | Grid hole, row letter + column | `bb:e15` |

## Architecture

```
breadboard_diagram.py  — CLI entry point, config parser, SVG compositor
components.py          — Procedural SVG component library (breadboard view)
router.py              — A* orthogonal wire routing engine
schematic.py           — IEEE schematic symbols and net renderer
```

### Wire Router

The breadboard-mode wire router uses A* pathfinding on a 4px grid:

- Orthogonal paths only (right angles, no diagonals)
- Component bodies are blocked zones (wires route around them)
- Already-routed wires create repulsion fields (adjacent cells penalized)
- Wires processed shortest-first for optimal routing priority
- Termination dots at both endpoints for unambiguous connections

### Schematic Mode

The schematic renderer transforms the same JSON config into a logical diagram:

- Breadboard components are omitted (they're physical-only)
- Power rail connections become VCC/GND symbols
- Components render as IEEE standard symbols (zigzag resistors, switch symbols, etc.)
- Connections render as labeled nets instead of routed wires

## Extending: Adding New Components

1. **Breadboard view**: Add a class in `components.py` inheriting from `Component`
2. **Schematic view**: Add a case in `schematic.py`'s `create_schematic_symbol()` factory
3. **Register**: Add the type key to `COMPONENT_REGISTRY` in `components.py`

Each component needs:
- `_compute_pins()`: Define pin names → (x, y) coordinates
- `render()`: Draw the SVG using `svgwrite`
- Width/height class attributes

## Dependencies

```
svgwrite    — SVG generation (required)
cairosvg    — SVG → PNG conversion (optional, for --png flag)
```
## License

MIT


## Created By

Cassette, aka maps
https://cassette.help
---


