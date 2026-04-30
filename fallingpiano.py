# import sys
# import math
# import pygame
# from dataclasses import dataclass
# from typing import List, Dict, Tuple, Optional

# import mido

# # ----------------------------
# # Config
# # ----------------------------
# WIN_W, WIN_H = 1200, 700
# FPS = 60

# # Piano range (standard 88-key)
# MIDI_MIN = 21   # A0
# MIDI_MAX = 108  # C8

# # Visual timing
# SECONDS_ON_SCREEN = 3.0   # notes appear this many seconds before they "hit" the keys
# FALL_SPEED = WIN_H / SECONDS_ON_SCREEN  # pixels per second

# # Layout
# KEYBOARD_H = 180
# LANE_TOP = 20
# LANE_BOTTOM = WIN_H - KEYBOARD_H - 10
# LANE_H = LANE_BOTTOM - LANE_TOP

# # ----------------------------
# # Data structures
# # ----------------------------
# @dataclass
# class NoteRect:
#     note: int
#     start: float  # seconds
#     end: float    # seconds
#     velocity: int

# # ----------------------------
# # MIDI parsing utilities
# # ----------------------------
# def load_midi_notes(path: str) -> Tuple[List[NoteRect], float]:
#     """
#     Parse a MIDI file into a list of NoteRect(start,end,note).
#     Uses a "merged track" timing approach with mido.
#     """
#     mid = mido.MidiFile(path)
#     tempo = 500000  # default 120 bpm in us/beat
#     ticks_per_beat = mid.ticks_per_beat

#     # Active notes: note -> list of (start_time, velocity)
#     active: Dict[int, List[Tuple[float, int]]] = {}
#     notes: List[NoteRect] = []

#     t = 0.0
#     for msg in mido.merge_tracks(mid.tracks):
#         t += mido.tick2second(msg.time, ticks_per_beat, tempo)

#         if msg.type == "set_tempo":
#             tempo = msg.tempo

#         if msg.type == "note_on" and msg.velocity > 0:
#             active.setdefault(msg.note, []).append((t, msg.velocity))

#         # note_off OR note_on with velocity 0 means note end
#         if msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
#             if msg.note in active and len(active[msg.note]) > 0:
#                 start_t, vel = active[msg.note].pop(0)
#                 end_t = t
#                 notes.append(NoteRect(note=msg.note, start=start_t, end=end_t, velocity=vel))

#     # Close any still-active notes at end time
#     total_len = t
#     for note, stack in active.items():
#         for start_t, vel in stack:
#             notes.append(NoteRect(note=note, start=start_t, end=total_len, velocity=vel))

#     # Sort by start time
#     notes.sort(key=lambda n: n.start)
#     return notes, total_len

# # ----------------------------
# # Piano geometry
# # ----------------------------
# BLACK_PCS = {1, 3, 6, 8, 10}  # C# D# F# G# A#

# def is_black(note: int) -> bool:
#     return (note % 12) in BLACK_PCS

# def midi_to_white_index(note: int) -> int:
#     """
#     Count how many white keys from MIDI_MIN to this note (inclusive if white).
#     Used to position keys and lanes uniformly by *white key* spacing.
#     """
#     idx = 0
#     for n in range(MIDI_MIN, note + 1):
#         if not is_black(n):
#             idx += 1
#     return idx - 1  # zero-based

# def count_white_keys() -> int:
#     return sum(1 for n in range(MIDI_MIN, MIDI_MAX + 1) if not is_black(n))

# def build_key_rects(piano_x: int, piano_y: int, piano_w: int, piano_h: int):
#     """
#     Returns:
#       white_keys: list of (note, rect)
#       black_keys: list of (note, rect)
#       note_to_lane: dict note -> (lane_x, lane_w)   # where falling bars should be drawn
#     """
#     white_count = count_white_keys()
#     white_w = piano_w / white_count
#     white_h = piano_h

#     # White keys
#     white_keys = []
#     note_to_white_x: Dict[int, float] = {}
#     for n in range(MIDI_MIN, MIDI_MAX + 1):
#         if not is_black(n):
#             wi = midi_to_white_index(n)
#             x = piano_x + wi * white_w
#             rect = pygame.Rect(int(x), piano_y, int(math.ceil(white_w)), white_h)
#             white_keys.append((n, rect))
#             note_to_white_x[n] = x

#     # Black keys
#     black_keys = []
#     black_w = white_w * 0.62
#     black_h = int(white_h * 0.62)

#     for n in range(MIDI_MIN, MIDI_MAX + 1):
#         if is_black(n):
#             # Black key sits between adjacent whites.
#             # For a given black note, find the previous white note.
#             prev = n - 1
#             while prev >= MIDI_MIN and is_black(prev):
#                 prev -= 1
#             if prev < MIDI_MIN or prev not in note_to_white_x:
#                 continue
#             x_left_white = note_to_white_x[prev]
#             x = x_left_white + white_w - black_w / 2.0
#             rect = pygame.Rect(int(x), piano_y, int(black_w), black_h)
#             black_keys.append((n, rect))

#     # Lanes: center on the "key position"
#     # For white notes: lane matches white key.
#     # For black notes: lane centered on black key, narrower.
#     note_to_lane: Dict[int, Tuple[float, float]] = {}
#     for n, rect in white_keys:
#         note_to_lane[n] = (rect.x, rect.w)
#     for n, rect in black_keys:
#         # narrower lane
#         w = rect.w
#         x = rect.x
#         note_to_lane[n] = (x, w)

#     return white_keys, black_keys, note_to_lane

# # ----------------------------
# # Rendering helpers
# # ----------------------------
# def clamp(v, a, b):
#     return max(a, min(b, v))

# def velocity_color(vel: int) -> Tuple[int, int, int]:
#     # Simple grayscale brightness based on velocity (0..127)
#     b = int(clamp(vel, 0, 127) / 127 * 255)
#     # slightly colored tint
#     return (80, 120, clamp(60 + b, 0, 255))

# def draw_piano(screen, white_keys, black_keys, active_notes: Dict[int, bool]):
#     # White keys
#     for note, rect in white_keys:
#         pressed = active_notes.get(note, False)
#         col = (230, 230, 230) if not pressed else (180, 220, 255)
#         pygame.draw.rect(screen, col, rect)
#         pygame.draw.rect(screen, (30, 30, 30), rect, 1)

#     # Black keys on top
#     for note, rect in black_keys:
#         pressed = active_notes.get(note, False)
#         col = (30, 30, 30) if not pressed else (80, 140, 200)
#         pygame.draw.rect(screen, col, rect)
#         pygame.draw.rect(screen, (10, 10, 10), rect, 1)

# def draw_lanes_bg(screen, lane_left: int, lane_right: int):
#     bg = pygame.Rect(lane_left, LANE_TOP, lane_right - lane_left, LANE_H)
#     pygame.draw.rect(screen, (18, 18, 22), bg)
#     pygame.draw.rect(screen, (50, 50, 60), bg, 1)

# def note_y_at_time(note_start: float, t: float) -> float:
#     """
#     A note bar "hits" the keyboard at y = LANE_BOTTOM when t == note_start.
#     It starts above the screen earlier by SECONDS_ON_SCREEN.
#     """
#     dt = note_start - t  # seconds until hit
#     y = LANE_BOTTOM - (dt * FALL_SPEED)
#     return y

# def draw_falling_notes(screen, notes: List[NoteRect], t: float, note_to_lane, active_notes: Dict[int, bool]):
#     """
#     Draw notes that are within the visible time window:
#       t - some margin  ..  t + SECONDS_ON_SCREEN
#     Also update active_notes for highlighting keys.
#     """
#     # Clear actives each frame; rebuild
#     active_notes.clear()

#     # Visible window: notes that hit within next SECONDS_ON_SCREEN,
#     # and notes that started slightly earlier but still have body on screen.
#     t_min = t - 1.0
#     t_max = t + SECONDS_ON_SCREEN

#     for nr in notes:
#         if nr.note < MIDI_MIN or nr.note > MIDI_MAX:
#             continue
#         if nr.start > t_max:
#             break
#         if nr.end < t_min:
#             continue

#         lane = note_to_lane.get(nr.note, None)
#         if lane is None:
#             continue
#         lane_x, lane_w = lane

#         # y position of the "hit line" at note start:
#         y_hit = note_y_at_time(nr.start, t)

#         # Height proportional to note duration
#         dur = max(0.02, nr.end - nr.start)
#         h = dur * FALL_SPEED

#         # The bar extends upward from the hit point
#         y_top = y_hit - h

#         # Only draw if intersects lane region
#         if y_top > LANE_BOTTOM or y_hit < LANE_TOP:
#             # completely off screen
#             pass
#         else:
#             rect = pygame.Rect(int(lane_x), int(y_top), int(lane_w), int(h))
#             col = velocity_color(nr.velocity)
#             pygame.draw.rect(screen, col, rect, border_radius=4)
#             pygame.draw.rect(screen, (20, 20, 25), rect, 1, border_radius=4)

#         # Active highlighting: if current time is within the note duration
#         if nr.start <= t <= nr.end:
#             active_notes[nr.note] = True

# def draw_timeline(screen, t: float, total: float, font):
#     txt = f"{t:6.2f}s / {total:6.2f}s"
#     surf = font.render(txt, True, (220, 220, 230))
#     screen.blit(surf, (20, 10))

#     # Progress bar
#     bar_x, bar_y, bar_w, bar_h = 200, 14, 300, 12
#     pygame.draw.rect(screen, (60, 60, 70), (bar_x, bar_y, bar_w, bar_h), border_radius=6)
#     if total > 0:
#         fill = int(bar_w * clamp(t / total, 0.0, 1.0))
#         pygame.draw.rect(screen, (120, 200, 160), (bar_x, bar_y, fill, bar_h), border_radius=6)

# def draw_help(screen, font, paused: bool):
#     lines = [
#         "Controls:",
#         "  Space: pause/play",
#         "  Left/Right: -/+ 5 seconds",
#         "  Up/Down:    -/+ 1 second",
#         "  Esc: quit",
#         f"Status: {'PAUSED' if paused else 'PLAYING'}"
#     ]
#     y = 34
#     for s in lines:
#         surf = font.render(s, True, (190, 190, 205))
#         screen.blit(surf, (20, y))
#         y += 18

# # ----------------------------
# # Main
# # ----------------------------
# def main():
#     if len(sys.argv) < 2:
#         print("Usage: python midi_falling_piano.py path/to/file.mid")
#         sys.exit(1)

#     midi_path = sys.argv[1]
#     notes, total_len = load_midi_notes(midi_path)
#     print(f"Loaded {len(notes)} notes, length ~ {total_len:.2f}s")

#     pygame.init()
#     screen = pygame.display.set_mode((WIN_W, WIN_H))
#     pygame.display.set_caption("MIDI Falling Piano (Rough GUI)")
#     clock = pygame.time.Clock()
#     font = pygame.font.SysFont("Arial", 16)

#     # Layout: piano spans most of the width
#     piano_x = 20
#     piano_w = WIN_W - 40
#     piano_y = WIN_H - KEYBOARD_H
#     piano_h = KEYBOARD_H - 20

#     white_keys, black_keys, note_to_lane = build_key_rects(piano_x, piano_y, piano_w, piano_h)

#     lane_left = piano_x
#     lane_right = piano_x + piano_w

#     t = 0.0
#     paused = False
#     active_notes: Dict[int, bool] = {}

#     running = True
#     while running:
#         dt = clock.tick(FPS) / 1000.0

#         # Events
#         for e in pygame.event.get():
#             if e.type == pygame.QUIT:
#                 running = False
#             elif e.type == pygame.KEYDOWN:
#                 if e.key == pygame.K_ESCAPE:
#                     running = False
#                 elif e.key == pygame.K_SPACE:
#                     paused = not paused
#                 elif e.key == pygame.K_LEFT:
#                     t = max(0.0, t - 5.0)
#                 elif e.key == pygame.K_RIGHT:
#                     t = min(total_len, t + 5.0)
#                 elif e.key == pygame.K_DOWN:
#                     t = max(0.0, t - 1.0)
#                 elif e.key == pygame.K_UP:
#                     t = min(total_len, t + 1.0)

#         if not paused:
#             t += dt
#             if t > total_len + 1.0:
#                 t = total_len + 1.0
#                 paused = True

#         # Render
#         screen.fill((10, 10, 12))
#         draw_lanes_bg(screen, lane_left, lane_right)

#         # Hit line
#         pygame.draw.line(screen, (200, 200, 210), (lane_left, LANE_BOTTOM), (lane_right, LANE_BOTTOM), 2)

#         # Falling notes + active tracking
#         draw_falling_notes(screen, notes, t, note_to_lane, active_notes)

#         # Piano
#         draw_piano(screen, white_keys, black_keys, active_notes)

#         # HUD
#         draw_timeline(screen, t, total_len, font)
#         draw_help(screen, font, paused)

#         pygame.display.flip()

#     pygame.quit()

# if __name__ == "__main__":
#     main()

import sys
import math
import re
import pygame
from dataclasses import dataclass
from typing import List, Dict, Tuple

import mido
try:
    import fluidsynth
except ImportError:
    fluidsynth = None

# ============================
# USER SETTINGS (EDIT IF NEEDED)
# ============================
SF2_PATH = "/Users/bijanbahrami/Downloads/FluidR3_GM/FluidR3_GM.sf2"

# ============================
# GUI / TIMING CONFIG
# ============================
WIN_W, WIN_H = 1200, 700
FPS = 60

# 88-key piano range
MIDI_MIN = 21   # A0
MIDI_MAX = 108  # C8

# Falling note visualization
SECONDS_ON_SCREEN = 3.0  # how many seconds ahead notes appear before "hit line"
KEYBOARD_H = 180
LANE_TOP = 20
LANE_BOTTOM = WIN_H - KEYBOARD_H - 10
LANE_H = LANE_BOTTOM - LANE_TOP

# Smooth seek tuning (animated scrolling)
SEEK_SCROLL_SPEED = 12.0  # seconds of timeline per real second during seek animation
SEEK_SNAP_EPS = 0.02      # snap to target if close

# Speed control bounds
SPEED_MIN = 0.25
SPEED_MAX = 3.0
SPEED_STEP_MULT = 1.10  # +/- changes multiplier by 10%

BLACK_PCS = {1, 3, 6, 8, 10}  # C# D# F# G# A#

# Teensy LED playback geometry/timing (must match firmware).
LED_TOTAL_COLS = 60
LED_TOTAL_ROWS = 24
LED_STRIKE_ROW = LED_TOTAL_ROWS - 2
LED_MS_PER_PIXEL = 110.0

# ============================
# DATA STRUCTURES
# ============================
@dataclass
class NoteRect:
    note: int
    start: float
    end: float
    velocity: int
    channel: int = 0
    col: int = -1

@dataclass
class MidiEvent:
    t: float
    kind: str  # note_on, note_off, program_change, control_change
    note: int = 0
    vel: int = 0
    channel: int = 0
    program: int = 0
    control: int = 0
    value: int = 0

# ============================
# MIDI PARSING (NOTES + EVENTS)
# ============================
def load_midi_notes_and_events(path: str) -> Tuple[List[NoteRect], List[MidiEvent], float]:
    mid = mido.MidiFile(path)
    tempo = 500000  # default 120 bpm
    tpb = mid.ticks_per_beat

    # active notes keyed by (channel, note)
    active: Dict[Tuple[int, int], List[Tuple[float, int]]] = {}
    notes: List[NoteRect] = []
    events: List[MidiEvent] = []

    t = 0.0
    for msg in mido.merge_tracks(mid.tracks):
        t += mido.tick2second(msg.time, tpb, tempo)

        if msg.type == "set_tempo":
            tempo = msg.tempo
            continue

        if msg.type == "note_on":
            if msg.velocity > 0:
                events.append(MidiEvent(t=t, kind="note_on", note=msg.note, vel=msg.velocity, channel=msg.channel))
                active.setdefault((msg.channel, msg.note), []).append((t, msg.velocity))
            else:
                # note_on with velocity 0 == note_off
                events.append(MidiEvent(t=t, kind="note_off", note=msg.note, vel=0, channel=msg.channel))
                key = (msg.channel, msg.note)
                if key in active and active[key]:
                    start_t, vel = active[key].pop(0)
                    notes.append(
                        NoteRect(
                            note=msg.note,
                            start=start_t,
                            end=t,
                            velocity=vel,
                            channel=msg.channel,
                            col=-1,
                        )
                    )

        elif msg.type == "note_off":
            events.append(MidiEvent(t=t, kind="note_off", note=msg.note, vel=0, channel=msg.channel))
            key = (msg.channel, msg.note)
            if key in active and active[key]:
                start_t, vel = active[key].pop(0)
                notes.append(
                    NoteRect(
                        note=msg.note,
                        start=start_t,
                        end=t,
                        velocity=vel,
                        channel=msg.channel,
                        col=-1,
                    )
                )

        elif msg.type == "program_change":
            events.append(MidiEvent(t=t, kind="program_change", channel=msg.channel, program=msg.program))

        elif msg.type == "control_change":
            events.append(MidiEvent(t=t, kind="control_change", channel=msg.channel, control=msg.control, value=msg.value))

    total_len = t

    # close any notes left on at end
    for (ch, note), stack in active.items():
        for start_t, vel in stack:
            notes.append(
                NoteRect(
                    note=note,
                    start=start_t,
                    end=total_len,
                    velocity=vel,
                    channel=ch,
                    col=-1,
                )
            )

    notes.sort(key=lambda n: n.start)
    events.sort(key=lambda e: e.t)
    return notes, events, total_len


def load_song_data_notes(path: str) -> Tuple[List[NoteRect], List[MidiEvent], float]:
    """
    Parse Teensy-generated src/song_data.h entries:
      {startMs, durationMs, col, midiNote},
    into NoteRects for the falling-piano renderer.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Capture each initializer row.
    matches = re.findall(r"\{(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\}", text)
    notes: List[NoteRect] = []
    for start_ms, duration_ms, col, midi_note in matches:
        start_s = int(start_ms) / 1000.0
        end_s = start_s + (int(duration_ms) / 1000.0)
        notes.append(
            NoteRect(
                note=int(midi_note),
                start=start_s,
                end=end_s,
                velocity=100,
                channel=0,
                col=int(col),
            )
        )

    notes.sort(key=lambda n: n.start)
    total_len = max((n.end for n in notes), default=0.0)
    events: List[MidiEvent] = []
    for n in notes:
        on_vel = int(clamp(n.velocity, 1, 127))
        events.append(MidiEvent(t=n.start, kind="note_on", note=n.note, vel=on_vel, channel=0))
        events.append(MidiEvent(t=n.end, kind="note_off", note=n.note, vel=0, channel=0))
    events.sort(key=lambda e: (e.t, 0 if e.kind == "note_off" else 1))
    return notes, events, total_len

# ============================
# PIANO GEOMETRY
# ============================
def is_black(note: int) -> bool:
    return (note % 12) in BLACK_PCS

def midi_to_white_index(note: int) -> int:
    idx = 0
    for n in range(MIDI_MIN, note + 1):
        if not is_black(n):
            idx += 1
    return idx - 1

def count_white_keys() -> int:
    return sum(1 for n in range(MIDI_MIN, MIDI_MAX + 1) if not is_black(n))

def build_key_rects(piano_x: int, piano_y: int, piano_w: int, piano_h: int):
    white_count = count_white_keys()
    white_w = piano_w / white_count
    white_h = piano_h

    white_keys = []
    note_to_white_x: Dict[int, float] = {}

    for n in range(MIDI_MIN, MIDI_MAX + 1):
        if not is_black(n):
            wi = midi_to_white_index(n)
            x = piano_x + wi * white_w
            rect = pygame.Rect(int(x), piano_y, int(math.ceil(white_w)), white_h)
            white_keys.append((n, rect))
            note_to_white_x[n] = x

    black_keys = []
    black_w = white_w * 0.62
    black_h = int(white_h * 0.62)

    for n in range(MIDI_MIN, MIDI_MAX + 1):
        if is_black(n):
            prev = n - 1
            while prev >= MIDI_MIN and is_black(prev):
                prev -= 1
            if prev < MIDI_MIN or prev not in note_to_white_x:
                continue

            x_left_white = note_to_white_x[prev]
            x = x_left_white + white_w - black_w / 2.0
            rect = pygame.Rect(int(x), piano_y, int(black_w), black_h)
            black_keys.append((n, rect))

    # Lanes for falling notes
    note_to_lane: Dict[int, Tuple[float, float]] = {}
    for n, rect in white_keys:
        note_to_lane[n] = (rect.x, rect.w)
    for n, rect in black_keys:
        note_to_lane[n] = (rect.x, rect.w)

    return white_keys, black_keys, note_to_lane

# ============================
# RENDERING HELPERS
# ============================
def clamp(v, a, b):
    return max(a, min(b, v))

def velocity_color(vel: int):
    b = int(clamp(vel, 0, 127) / 127 * 255)
    return (80, 120, clamp(60 + b, 0, 255))

def fall_speed_px_per_s():
    return WIN_H / SECONDS_ON_SCREEN

def note_y_at_time(note_start: float, t: float) -> float:
    dt = note_start - t  # seconds until it hits
    return LANE_BOTTOM - (dt * fall_speed_px_per_s())

def draw_lanes_bg(screen, lane_left: int, lane_right: int):
    bg = pygame.Rect(lane_left, LANE_TOP, lane_right - lane_left, LANE_H)
    pygame.draw.rect(screen, (18, 18, 22), bg)
    pygame.draw.rect(screen, (50, 50, 60), bg, 1)

def draw_falling_notes(screen, notes: List[NoteRect], t: float, note_to_lane, active_notes: Dict[int, bool]):
    active_notes.clear()

    t_min = t - 1.0
    t_max = t + SECONDS_ON_SCREEN

    for nr in notes:
        if nr.note < MIDI_MIN or nr.note > MIDI_MAX:
            continue
        if nr.start > t_max:
            break
        if nr.end < t_min:
            continue

        lane = note_to_lane.get(nr.note)
        if lane is None:
            continue
        lane_x, lane_w = lane

        y_hit = note_y_at_time(nr.start, t)
        dur = max(0.02, nr.end - nr.start)
        h = dur * fall_speed_px_per_s()
        y_top = y_hit - h

        if not (y_top > LANE_BOTTOM or y_hit < LANE_TOP):
            rect = pygame.Rect(int(lane_x), int(y_top), int(lane_w), int(h))
            col = velocity_color(nr.velocity)
            pygame.draw.rect(screen, col, rect, border_radius=4)
            pygame.draw.rect(screen, (20, 20, 25), rect, 1, border_radius=4)

        if nr.start <= t <= nr.end:
            active_notes[nr.note] = True


def draw_led_synced_notes(
    screen,
    notes: List[NoteRect],
    play_t_s: float,
    lane_left: int,
    lane_right: int,
    active_notes: Dict[int, bool],
):
    """
    Mirror Teensy timing/geometry exactly:
      headY = STRIKE_ROW - (deltaMs / MS_PER_PIXEL)
      tailY = headY - (durationMs / MS_PER_PIXEL)
    and only draw rows that intersect the 24-row LED grid.
    """
    active_notes.clear()
    lane_w = lane_right - lane_left
    col_w = lane_w / LED_TOTAL_COLS
    row_h = LANE_H / LED_TOTAL_ROWS
    now_ms = play_t_s * 1000.0

    for nr in notes:
        if nr.col < 0 or nr.col >= LED_TOTAL_COLS:
            continue

        start_ms = nr.start * 1000.0
        dur_ms = max(20.0, (nr.end - nr.start) * 1000.0)

        delta_ms = start_ms - now_ms
        head_row = LED_STRIKE_ROW - (delta_ms / LED_MS_PER_PIXEL)
        tail_row = head_row - (dur_ms / LED_MS_PER_PIXEL)

        # If the note body is fully outside LED rows, skip.
        if head_row < 0.0 or tail_row > (LED_TOTAL_ROWS - 1):
            continue

        x = lane_left + nr.col * col_w
        y_top = LANE_TOP + max(0.0, tail_row) * row_h
        y_bottom = LANE_TOP + min(float(LED_TOTAL_ROWS - 1), head_row) * row_h
        h = max(1.0, y_bottom - y_top + row_h)

        rect = pygame.Rect(int(x), int(y_top), max(1, int(col_w)), int(h))
        pygame.draw.rect(screen, (90, 170, 255), rect)

        # Match key highlight to effective "pressed" interval at strike.
        if nr.start <= play_t_s <= nr.end:
            active_notes[nr.note] = True


def draw_led_column_overlay(screen, notes: List[NoteRect], t: float, lane_left: int, lane_right: int):
    # Mirror the Teensy lane geometry: 5 panels * 12 columns = 60.
    total_cols = 60
    lane_w = lane_right - lane_left
    col_w = lane_w / total_cols
    t_min = t - 1.0
    t_max = t + SECONDS_ON_SCREEN

    overlay = pygame.Surface((lane_w, LANE_H), pygame.SRCALPHA)
    for nr in notes:
        if nr.col < 0 or nr.col >= total_cols:
            continue
        if nr.start > t_max:
            break
        if nr.end < t_min:
            continue

        y_hit = note_y_at_time(nr.start, t)
        dur = max(0.02, nr.end - nr.start)
        h = dur * fall_speed_px_per_s()
        y_top = y_hit - h
        if y_top > LANE_BOTTOM or y_hit < LANE_TOP:
            continue

        x = nr.col * col_w
        rect = pygame.Rect(int(x), int(y_top - LANE_TOP), max(1, int(col_w)), int(h))
        pygame.draw.rect(overlay, (255, 170, 30, 70), rect)
        pygame.draw.rect(overlay, (255, 210, 110, 120), rect, 1)

    screen.blit(overlay, (lane_left, LANE_TOP))

def draw_piano(screen, white_keys, black_keys, active_notes: Dict[int, bool]):
    for note, rect in white_keys:
        pressed = active_notes.get(note, False)
        col = (230, 230, 230) if not pressed else (180, 220, 255)
        pygame.draw.rect(screen, col, rect)
        pygame.draw.rect(screen, (30, 30, 30), rect, 1)

    for note, rect in black_keys:
        pressed = active_notes.get(note, False)
        col = (30, 30, 30) if not pressed else (80, 140, 200)
        pygame.draw.rect(screen, col, rect)
        pygame.draw.rect(screen, (10, 10, 10), rect, 1)

def draw_hud(
    screen,
    font,
    t: float,
    total: float,
    speed: float,
    paused: bool,
    seeking: bool,
    show_overlay: bool,
    led_sync_mode: bool,
):
    txt = f"{t:6.2f}s / {total:6.2f}s   speed: {speed:.2f}x   {'PAUSED' if paused else 'PLAYING'}"
    if seeking:
        txt += "   SEEKING…"
    screen.blit(font.render(txt, True, (220, 220, 230)), (20, 10))

    lines = [
        "Controls:",
        "  Space: play/pause (stops audio)",
        "  +/- : speed down/up (audio + visuals)",
        "  Left/Right: seek -/+ 5s (smooth scroll)",
        "  Up/Down:    seek -/+ 1s (smooth scroll)",
        "  Enter: resume immediately after seeking",
        f"  O: toggle LED-column overlay ({'ON' if show_overlay else 'OFF'})",
        f"  LED sync mode: {'ON' if led_sync_mode else 'OFF'}",
        "  Esc: quit",
    ]
    y = 34
    for s in lines:
        screen.blit(font.render(s, True, (190, 190, 205)), (20, y))
        y += 18

# ============================
# FLUIDSYNTH AUDIO ENGINE
# ============================
class FluidMidiOut:
    def __init__(self, sf2_path: str):
        if fluidsynth is None:
            raise RuntimeError("pyfluidsynth is not installed.")
        self.fs = fluidsynth.Synth()
        self.fs.start(driver="coreaudio")  # macOS audio backend
        self.sfid = self.fs.sfload(sf2_path)

        # default to Acoustic Grand Piano on all channels
        for ch in range(16):
            self.fs.program_select(ch, self.sfid, 0, 0)

    def close(self):
        self.all_notes_off()
        self.fs.delete()

    def note_on(self, note: int, vel: int, ch: int):
        self.fs.noteon(ch, note, vel)

    def note_off(self, note: int, ch: int):
        self.fs.noteoff(ch, note)

    def program_change(self, program: int, ch: int):
        self.fs.program_select(ch, self.sfid, 0, program)

    def control_change(self, control: int, value: int, ch: int):
        self.fs.cc(ch, control, value)

    def all_notes_off(self):
        for ch in range(16):
            self.fs.cc(ch, 123, 0)  # CC 123 = All Notes Off

# ============================
# MAIN
# ============================
def main():
    if len(sys.argv) < 2:
        print("Usage: python fallingpiano.py /path/to/file.mid|song_data.h")
        sys.exit(1)

    input_path = sys.argv[1]

    # Load either a MIDI file or Teensy song_data.h.
    from_song_data = input_path.lower().endswith(".h")
    if from_song_data:
        notes, events, total_len = load_song_data_notes(input_path)
        print(f"Loaded {len(notes)} notes from song_data.h, length ~ {total_len:.2f}s")
    else:
        notes, events, total_len = load_midi_notes_and_events(input_path)
        print(f"Loaded {len(notes)} notes, {len(events)} events, length ~ {total_len:.2f}s")

    # Start audio for both MIDI and song_data.h modes.
    # In song_data mode, events are synthesized from NoteRect start/end times.
    midi_out = None
    try:
        midi_out = FluidMidiOut(SF2_PATH)
        print("Audio: FluidSynth OK.")
    except Exception as e:
        print("\nWARNING: FluidSynth audio unavailable; continuing with visuals only.")
        print("Most common causes:")
        print("  - SF2_PATH is wrong")
        print("  - fluidsynth not installed (brew install fluidsynth)")
        print("  - pyfluidsynth not installed (pip install pyfluidsynth)")
        print("\nDetails:", e)

    # Start GUI
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("MIDI Falling Piano (Audio + Speed + Smooth Seek)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 16)

    piano_x = 20
    piano_w = WIN_W - 40
    piano_y = WIN_H - KEYBOARD_H
    piano_h = KEYBOARD_H - 20

    white_keys, black_keys, note_to_lane = build_key_rects(piano_x, piano_y, piano_w, piano_h)
    lane_left = piano_x
    lane_right = piano_x + piano_w

    # timeline state
    play_t = 0.0
    target_t = 0.0
    seeking = False
    paused = False
    speed = 1.0
    show_led_overlay = False
    led_sync_mode = from_song_data

    # event scheduler state
    event_idx = 0

    def reset_audio_to_time(new_t: float):
        nonlocal event_idx
        if midi_out is None:
            return
        midi_out.all_notes_off()

        # binary search first event with t >= new_t
        lo, hi = 0, len(events)
        while lo < hi:
            mid = (lo + hi) // 2
            if events[mid].t < new_t:
                lo = mid + 1
            else:
                hi = mid
        event_idx = lo

    reset_audio_to_time(0.0)

    active_notes: Dict[int, bool] = {}
    running = True

    while running:
        dt_real = clock.tick(FPS) / 1000.0

        # ---------- input ----------
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False

                elif e.key == pygame.K_SPACE:
                    paused = not paused
                    if paused and midi_out is not None:
                        midi_out.all_notes_off()

                elif e.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    speed = clamp(speed * SPEED_STEP_MULT, SPEED_MIN, SPEED_MAX)

                elif e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed = clamp(speed / SPEED_STEP_MULT, SPEED_MIN, SPEED_MAX)

                elif e.key == pygame.K_LEFT:
                    base = target_t if seeking else play_t
                    target_t = max(0.0, base - 5.0)
                    seeking = True
                    paused = True
                    reset_audio_to_time(target_t)

                elif e.key == pygame.K_RIGHT:
                    base = target_t if seeking else play_t
                    target_t = min(total_len, base + 5.0)
                    seeking = True
                    paused = True
                    reset_audio_to_time(target_t)

                elif e.key == pygame.K_DOWN:
                    base = target_t if seeking else play_t
                    target_t = max(0.0, base - 1.0)
                    seeking = True
                    paused = True
                    reset_audio_to_time(target_t)

                elif e.key == pygame.K_UP:
                    base = target_t if seeking else play_t
                    target_t = min(total_len, base + 1.0)
                    seeking = True
                    paused = True
                    reset_audio_to_time(target_t)

                elif e.key == pygame.K_RETURN:
                    if seeking:
                        play_t = target_t
                        seeking = False
                        paused = False
                        reset_audio_to_time(play_t)
                elif e.key == pygame.K_o:
                    show_led_overlay = not show_led_overlay

        # ---------- timeline update ----------
        if seeking:
            direction = 1.0 if target_t > play_t else -1.0
            step = SEEK_SCROLL_SPEED * dt_real
            if abs(target_t - play_t) <= max(SEEK_SNAP_EPS, step):
                play_t = target_t
            else:
                play_t += direction * step

        elif not paused:
            # speed affects BOTH visuals + audio because audio scheduling uses play_t
            play_t += dt_real * speed
            if play_t > total_len + 1.0:
                play_t = total_len + 1.0
                paused = True
                if midi_out is not None:
                    midi_out.all_notes_off()

        # ---------- audio dispatch ----------
        if midi_out is not None and (not paused) and (not seeking):
            while event_idx < len(events) and events[event_idx].t <= play_t:
                ev = events[event_idx]
                if ev.kind == "note_on":
                    midi_out.note_on(ev.note, ev.vel, ev.channel)
                elif ev.kind == "note_off":
                    midi_out.note_off(ev.note, ev.channel)
                elif ev.kind == "program_change":
                    midi_out.program_change(ev.program, ev.channel)
                elif ev.kind == "control_change":
                    midi_out.control_change(ev.control, ev.value, ev.channel)
                event_idx += 1

        # ---------- render ----------
        screen.fill((10, 10, 12))
        draw_lanes_bg(screen, lane_left, lane_right)

        # hit line
        pygame.draw.line(screen, (200, 200, 210), (lane_left, LANE_BOTTOM), (lane_right, LANE_BOTTOM), 2)

        if led_sync_mode:
            draw_led_synced_notes(screen, notes, play_t, lane_left, lane_right, active_notes)
        else:
            draw_falling_notes(screen, notes, play_t, note_to_lane, active_notes)
        if show_led_overlay:
            draw_led_column_overlay(screen, notes, play_t, lane_left, lane_right)
        draw_piano(screen, white_keys, black_keys, active_notes)
        draw_hud(screen, font, play_t, total_len, speed, paused, seeking, show_led_overlay, led_sync_mode)

        pygame.display.flip()

    # cleanup
    try:
        if midi_out is not None:
            midi_out.close()
    except Exception:
        pass
    pygame.quit()

if __name__ == "__main__":
    main()
    