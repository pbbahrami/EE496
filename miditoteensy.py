import mido
import argparse

# ===== USER SETTINGS =====
MIDI_FILE = "Queen - Bohemian Rhapsody.mid"
OUTPUT_FILE = "src/song_data.h"

# Fixed 5-octave window (B..A#) for 60 columns:
# C2 (36) through B6 (95) => 60 columns.
BASE_NOTE = 36
NUM_COLUMNS = 60
MAX_NOTE = BASE_NOTE + NUM_COLUMNS - 1
MIN_DURATION_MS = 60

# Keep only this track from your printed summary
TARGET_TRACK_INDEX = 3

# Keep full chords for guided mode hold validation.
KEEP_ONLY_HIGHEST_NOTE_PER_START = False


def build_tempo_map(mid):
    merged = mido.merge_tracks(mid.tracks)
    ticks_per_beat = mid.ticks_per_beat

    tempo_changes = [(0, 500000)]  # default 120 BPM
    abs_tick = 0

    for msg in merged:
        abs_tick += msg.time
        if msg.type == "set_tempo":
            tempo_changes.append((abs_tick, msg.tempo))

    return tempo_changes, ticks_per_beat


def ticks_to_ms(target_tick, tempo_changes, ticks_per_beat):
    total_seconds = 0.0

    for i in range(len(tempo_changes)):
        start_tick, tempo = tempo_changes[i]

        if i + 1 < len(tempo_changes):
            next_tick = tempo_changes[i + 1][0]
        else:
            next_tick = target_tick

        if target_tick <= start_tick:
            break

        segment_end = min(target_tick, next_tick)
        delta_ticks = segment_end - start_tick

        if delta_ticks > 0:
            total_seconds += mido.tick2second(delta_ticks, ticks_per_beat, tempo)

        if target_tick < next_tick:
            break

    return int(total_seconds * 1000)


def simplify_events(events):
    if not KEEP_ONLY_HIGHEST_NOTE_PER_START:
        return events

    grouped = {}
    for ev in events:
        start_ms, duration_ms, col, midi_note = ev
        if start_ms not in grouped:
            grouped[start_ms] = ev
        else:
            if midi_note > grouped[start_ms][3]:
                grouped[start_ms] = ev

    simplified = list(grouped.values())
    simplified.sort(key=lambda x: x[0])
    return simplified


def parse_selected_track(mid, track_index):
    if track_index < 0 or track_index >= len(mid.tracks):
        raise ValueError(f"Track index {track_index} out of range (0..{len(mid.tracks)-1})")

    tempo_changes, ticks_per_beat = build_tempo_map(mid)
    track = mid.tracks[track_index]

    abs_tick = 0
    active_notes = {}
    events = []
    seen_notes = []

    for msg in track:
        abs_tick += msg.time

        if hasattr(msg, "channel") and msg.channel == 9:
            continue

        if msg.type == "note_on" and msg.velocity > 0:
            seen_notes.append(msg.note)

            if BASE_NOTE <= msg.note <= MAX_NOTE:
                ch = msg.channel if hasattr(msg, "channel") else -1
                active_notes[(msg.note, ch)] = abs_tick

        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            ch = msg.channel if hasattr(msg, "channel") else -1
            key = (msg.note, ch)

            if BASE_NOTE <= msg.note <= MAX_NOTE and key in active_notes:
                start_tick = active_notes.pop(key)
                end_tick = abs_tick

                start_ms = ticks_to_ms(start_tick, tempo_changes, ticks_per_beat)
                end_ms = ticks_to_ms(end_tick, tempo_changes, ticks_per_beat)

                duration_ms = max(end_ms - start_ms, MIN_DURATION_MS)
                col = msg.note - BASE_NOTE

                events.append((start_ms, duration_ms, col, msg.note))

    events.sort(key=lambda x: x[0])

    if events:
        first_start = events[0][0]
        events = [(start - first_start, dur, col, note) for start, dur, col, note in events]

    simplified = simplify_events(events)

    if seen_notes:
        print(f"Track {track_index} lowest note: {min(seen_notes)}")
        print(f"Track {track_index} highest note: {max(seen_notes)}")

    print(f"Track {track_index} raw in-range events: {len(events)}")
    print(f"Track {track_index} simplified events: {len(simplified)}")

    return simplified


def write_header(events, out_path):
    with open(out_path, "w") as f:
        f.write("#pragma once\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write("struct NoteEvent {\n")
        f.write("    uint32_t startMs;\n")
        f.write("    uint32_t durationMs;\n")
        f.write("    uint8_t col;\n")
        f.write("    uint8_t midiNote;\n")
        f.write("};\n\n")

        f.write(f"const uint16_t SONG_EVENT_COUNT = {len(events)};\n")
        f.write("const NoteEvent songEvents[] = {\n")
        for start_ms, duration_ms, col, midi_note in events:
            f.write(f"    {{{start_ms}, {duration_ms}, {col}, {midi_note}}},\n")
        f.write("};\n")

    print(f"Wrote {len(events)} events to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert one MIDI track to Teensy song_data.h")
    parser.add_argument("--midi", default=MIDI_FILE, help="Input MIDI file path")
    parser.add_argument("--track", type=int, default=TARGET_TRACK_INDEX, help="Track index to extract")
    parser.add_argument("--out", default=OUTPUT_FILE, help="Output header path")
    args = parser.parse_args()

    mid = mido.MidiFile(args.midi)
    events = parse_selected_track(mid, args.track)
    write_header(events, args.out)