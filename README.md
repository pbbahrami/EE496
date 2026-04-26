# Capstone Teensy Dual-Panel Piano Visualizer

This project runs on a Teensy 4.1 using PlatformIO + Arduino framework + FastLED.
It renders note lanes on two 12x24 LED panels (treated as one virtual 24x24 display).

## Current Project Status

- Architecture is now modular (no large logic blob in `main.cpp`).
- Playback engine supports:
  - continuous progression by elapsed milliseconds
  - guided wait mode (pauses progression when a note reaches strike line until correct key event)
- Rendering supports sustained notes by using `durationMs` as vertical note length.
- Panel/global coordinate mapping is isolated to mapping/display modules.
- `main.cpp` is orchestration-only (setup, update, input handoff, render call).
- Build verification from the chat environment was blocked by sandbox permissions; run locally with PlatformIO CLI to verify on your machine.

## File Hierarchy

```text
Capstone/
  platformio.ini               # PlatformIO board/env configuration
  src/
    main.cpp                   # Thin application loop and serial input bridge
    song_data.h                # Generated note events: startMs, durationMs, col, midiNote
    playback.cpp               # Time progression + guided wait state machine
    renderer.cpp               # All frame drawing logic
    mapping.cpp                # Pure coordinate/index mapping
    display.cpp                # LED buffers and panel writes via mapping
  include/
    config.h                   # Shared constants (pins, dimensions, timing)
    playback.h                 # Playback engine API + RenderNote
    renderer.h                 # Renderer API
    mapping.h                  # Mapping API
    display.h                  # Display API
```

## Module Responsibilities

### `src/main.cpp` (orchestration only)

- Initializes serial + display.
- Owns one `PlaybackEngine` instance.
- Per loop:
  1. updates playback time/state
  2. reads key input from serial and reports it to playback engine
  3. collects renderable notes from playback
  4. calls renderer with note list and pause status
- Does **not** contain mapping math or rendering details.

### `src/playback.cpp` + `include/playback.h`

- Maintains song time (`songTimeMs_`) and playback mode.
- **Continuous mode:** advances by measured elapsed wall-clock milliseconds each frame.
- **Guided wait mode:** when a note reaches strike time, progression pauses; resumes only after matching key column is reported.
- Converts song events into renderer-friendly note geometry:
  - head position from event timing
  - tail position from note duration
- Keeps state for unresolved/waiting note indexes.

### `src/renderer.cpp` + `include/renderer.h`

- Owns visual decisions only:
  - note color/intensity profile
  - strike line
  - panel divider
  - sustain-body drawing from head/tail
- Consumes precomputed `RenderNote` data from playback.
- Calls display module functions to write pixels and present frame.

### `src/mapping.cpp` + `include/mapping.h`

- Handles coordinate conversion only:
  - local XY -> serpentine LED index
  - global XY -> panel + local XY
- Contains no animation, timing, or hardware setup.

### `src/display.cpp` + `include/display.h`

- Owns the FastLED buffers for each panel.
- Initializes FastLED strips and brightness.
- Applies global pixel writes by calling mapping functions.
- Shows frame via `FastLED.show()`.

### `src/song_data.h`

- Song timeline data (array of `NoteEvent`).
- Fields:
  - `startMs`: note onset in song time
  - `durationMs`: sustain length
  - `col`: target display lane (global x)
  - `midiNote`: source note reference (currently metadata)

## Data Flow (Frame-by-Frame)

1. `main.cpp` calls `PlaybackEngine::update(millis())`
2. Playback advances time or pauses (guided wait)
3. `main.cpp` passes user key events into `PlaybackEngine::reportKeyEvent(...)`
4. `PlaybackEngine::collectRenderableNotes(...)` outputs visible `RenderNote[]`
5. `renderFrame(...)` draws notes/strike line/divider through display module
6. Display module maps coordinates and pushes LEDs

## How Multi-File Firmware Flashing Works (Teensy + PlatformIO)

Even though your code is split across many `.cpp/.h` files, flashing is still a single firmware upload.

### Build phase

- PlatformIO scans `src/` and compiles each `.cpp` into an object file.
- Headers in `include/` are included during compilation, but are not compiled alone.
- Linker combines all object files + libraries into one ELF/BIN/HEX firmware image.
- Result: one final firmware artifact for the selected env (here `env:teensy41`).

### Upload phase

- `pio run -t upload` (or IDE Upload button) invokes Teensy upload tooling (`teensy-cli` from `platformio.ini`).
- Bootloader on Teensy receives the single built image.
- Device reboots into the new firmware.

### Practical implication

- You can organize code across as many files/modules as needed.
- Teensy does not receive files individually; it receives one linked program image.

## Typical Team Workflow

1. Pull latest project code.
2. Edit module(s) in `src/` + API in `include/`.
3. Build:
   - `pio run`
4. Flash:
   - `pio run -t upload`
5. Monitor serial:
   - `pio device monitor -b 115200`
6. Test:
   - continuous mode timing flow
   - guided wait pause/resume
   - sustain rendering for long `durationMs`

## Guided Wait Testing Notes

- Current sample input is via serial line:
  - send `17` or `c17` to report lane 17 key press
- In `main.cpp`, default start mode is continuous:
  - `gPlayback.begin(PlaybackMode::Continuous, millis());`
- To test guided mode immediately, switch to:
  - `gPlayback.begin(PlaybackMode::GuidedWait, millis());`
  - or call `gPlayback.setMode(PlaybackMode::GuidedWait);`

## Embedded Readability/Practicality Guidelines Used

- Clear module boundaries and small public interfaces.
- No architecture rollback into `main.cpp`.
- No dynamic allocation in frame path.
- Fixed-size render note buffer in `main.cpp`.
- Rendering kept separate from timing/input state machine.

## Known Follow-Ups (Optional)

- Add a runtime serial command to toggle modes (`continuous`/`guided`) without recompiling.
- Add hit windows (early/late tolerance) if you want rhythm-game-like scoring.
- Add serial debug telemetry (song time, pause state, waiting lane).
# EE496
