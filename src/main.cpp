#include <Arduino.h>
#include <stdio.h>
#include <USBHost_t36.h>

#include "config.h"
#include "display.h"
#include "playback.h"
#include "renderer.h"

namespace {
PlaybackEngine gPlayback;
RenderNote gVisibleNotes[96];
uint8_t gCurrentBrightness = BRIGHTNESS;
constexpr float BASE_BPM = 120.0f;
USBHost gUsbHost;
USBHub gHub1(gUsbHost);
USBHub gHub2(gUsbHost);
MIDIDevice gMidiIn(gUsbHost);
bool gLastMidiAttached = false;
bool gLastHub1Attached = false;
bool gLastHub2Attached = false;
uint32_t gLastHostHeartbeatMs = 0;

void runStartupPanelTest() {
    const CRGB testColors[NUM_PANELS] = {
        CRGB::Red, CRGB::Green, CRGB::Blue, CRGB::Yellow, CRGB::Purple};

    for (int p = 0; p < NUM_PANELS; ++p) {
        clearPanels();
        const int xStart = p * PANEL_WIDTH;
        const int xEnd = xStart + PANEL_WIDTH;
        for (int x = xStart; x < xEnd; ++x) {
            for (int y = 0; y < TOTAL_HEIGHT; ++y) {
                addGlobalXY(x, y, testColors[p]);
            }
        }
        showPanels();
        delay(800);
    }

    clearPanels();
    showPanels();
}

bool readSerialLine(String &lineOut) {
    if (!Serial.available()) {
        return false;
    }

    lineOut = Serial.readStringUntil('\n');
    lineOut.trim();
    return lineOut.length() > 0;
}

bool isAllDigits(const String &s) {
    if (s.length() == 0) {
        return false;
    }
    for (unsigned int i = 0; i < s.length(); ++i) {
        if (s[i] < '0' || s[i] > '9') {
            return false;
        }
    }
    return true;
}

bool parseColumnLine(String line, uint8_t &colOut) {
    if (line.length() > 0 && (line[0] == 'c' || line[0] == 'C')) {
        line.remove(0, 1);
    }
    if (!isAllDigits(line)) {
        return false;
    }
    const int col = line.toInt();
    if (col < 0 || col >= TOTAL_WIDTH) {
        return false;
    }
    colOut = static_cast<uint8_t>(col);
    return true;
}

bool midiNoteToColumn(uint8_t midiNote, uint8_t &colOut) {
    // Must match converter mapping window C2..B6 (36..95) for 60 columns.
    static constexpr int kBaseNote = 36;
    static constexpr int kMaxNote = 95;
    if (midiNote < kBaseNote || midiNote > kMaxNote) {
        return false;
    }
    const int col = static_cast<int>(midiNote) - kBaseNote;
    if (col < 0 || col >= TOTAL_WIDTH) {
        return false;
    }
    colOut = static_cast<uint8_t>(col);
    return true;
}

void onMidiNoteOn(byte channel, byte note, byte velocity) {
    Serial.printf("MIDI NOTE_ON ch=%u note=%u vel=%u\n", channel, note, velocity);
    if (velocity == 0) {
        uint8_t upCol = 0;
        if (midiNoteToColumn(note, upCol)) {
            gPlayback.reportKeyUp(upCol);
        }
        return;
    }
    uint8_t col = 0;
    if (midiNoteToColumn(note, col)) {
        const bool accepted = gPlayback.reportKeyEvent(col);
        Serial.printf("MIDI MAP col=%u accepted=%d\n", col, accepted ? 1 : 0);
        if (gPlayback.mode() == PlaybackMode::Continuous && liveFeedbackEnabled()) {
            const uint64_t req = gPlayback.requiredMaskNow();
            const bool correct = ((req >> col) & uint64_t{1}) != 0;
            pushLiveFeedback(col, correct);
        }
    }
}

void onMidiNoteOff(byte channel, byte note, byte velocity) {
    (void)velocity;
    Serial.printf("MIDI NOTE_OFF ch=%u note=%u\n", channel, note);
    uint8_t col = 0;
    if (midiNoteToColumn(note, col)) {
        gPlayback.reportKeyUp(col);
    }
}

void onMidiControlChange(byte channel, byte control, byte value) {
    Serial.printf("MIDI CC ch=%u cc=%u val=%u\n", channel, control, value);
}

void onMidiPitchBend(byte channel, int value) {
    Serial.printf("MIDI PITCH ch=%u val=%d\n", channel, value);
}

ColorMode parseColorModeToken(String token) {
    token.trim();
    token.toUpperCase();
    if (token == "0" || token == "FIXED") {
        return ColorMode::Fixed;
    }
    if (token == "1" || token == "PITCH" || token == "PITCHCLASS") {
        return ColorMode::PitchClass;
    }
    if (token == "2" || token == "RAINBOW") {
        return ColorMode::Rainbow;
    }
    if (token == "3" || token == "ALT" || token == "ALTERNATE") {
        return ColorMode::Alternate;
    }
    return colorMode();
}

void handleControlCommand(const String &line) {
    String upper = line;
    upper.toUpperCase();

    if (upper == "HELP") {
        Serial.println("Commands: PLAY, PAUSE, TOGGLE, STOP, SEEKMS <ms>, BPM <40-260>, SPD <0.2-3.0>, BRI <0-255>, MODE <fixed|pitch|rainbow|alternate>, PMODE <continuous|guided>, SONG <0-10>, LIVEFB <0|1>, BASE <r g b>, STATUS, <col>");
        return;
    }

    if (upper == "PLAY") {
        gPlayback.setPlaying(true);
        Serial.println("playing=1");
        return;
    }

    if (upper == "PAUSE") {
        gPlayback.setPlaying(false);
        Serial.println("playing=0");
        return;
    }

    if (upper == "TOGGLE") {
        const bool next = !gPlayback.isPlaying();
        gPlayback.setPlaying(next);
        Serial.printf("playing=%d\n", next ? 1 : 0);
        return;
    }

    if (upper == "STOP") {
        gPlayback.setPlaying(false);
        gPlayback.resetSongTime();
        Serial.println("stopped=1");
        return;
    }

    if (upper.startsWith("SEEKMS ")) {
        const int split = line.indexOf(' ');
        const uint32_t target = static_cast<uint32_t>(max(0, line.substring(split + 1).toInt()));
        gPlayback.seekToMs(target);
        Serial.printf("seekms=%lu\n", static_cast<unsigned long>(target));
        return;
    }

    if (upper.startsWith("BRI ") || upper.startsWith("BRIGHTNESS ")) {
        const int split = line.indexOf(' ');
        const int v = line.substring(split + 1).toInt();
        gCurrentBrightness = static_cast<uint8_t>(constrain(v, 0, 255));
        setDisplayBrightness(gCurrentBrightness);
        Serial.printf("brightness=%u\n", gCurrentBrightness);
        return;
    }

    if (upper.startsWith("SPD ") || upper.startsWith("SPEED ")) {
        const int split = line.indexOf(' ');
        float s = line.substring(split + 1).toFloat();
        if (s <= 0.0f) {
            s = 1.0f;
        }
        gPlayback.setSpeed(s);
        Serial.printf("speed=%.2f\n", gPlayback.speed());
        return;
    }

    if (upper.startsWith("BPM ")) {
        const int split = line.indexOf(' ');
        float bpm = line.substring(split + 1).toFloat();
        if (bpm < 40.0f) {
            bpm = 40.0f;
        }
        if (bpm > 260.0f) {
            bpm = 260.0f;
        }
        gPlayback.setSpeed(bpm / BASE_BPM);
        Serial.printf("bpm=%.1f speed=%.2f\n", bpm, gPlayback.speed());
        return;
    }

    if (upper.startsWith("MODE ") || upper.startsWith("COLORMODE ")) {
        const int split = line.indexOf(' ');
        const ColorMode m = parseColorModeToken(line.substring(split + 1));
        setColorMode(m);
        // Trigger immediate visual refresh after mode change.
        renderFrame(gVisibleNotes, 0, gPlayback.isGuidedPaused());
        Serial.printf("mode=%d\n", static_cast<int>(m));
        return;
    }

    if (upper.startsWith("LIVEFB ")) {
        const int split = line.indexOf(' ');
        const int en = line.substring(split + 1).toInt();
        setLiveFeedbackEnabled(en != 0);
        Serial.printf("livefb=%d\n", liveFeedbackEnabled() ? 1 : 0);
        return;
    }

    if (upper.startsWith("PMODE ") || upper.startsWith("PLAYMODE ")) {
        const int split = line.indexOf(' ');
        String tok = line.substring(split + 1);
        tok.trim();
        tok.toUpperCase();
        if (tok == "GUIDED" || tok == "1") {
            gPlayback.setMode(PlaybackMode::GuidedWait);
        } else {
            gPlayback.setMode(PlaybackMode::Continuous);
        }
        Serial.printf("playmode=%s\n", gPlayback.mode() == PlaybackMode::GuidedWait ? "guided" : "continuous");
        return;
    }

    if (upper.startsWith("SONG ")) {
        const int split = line.indexOf(' ');
        const int idx = line.substring(split + 1).toInt();
        const uint8_t n = gPlayback.songCount();
        const int hi = (n == 0) ? 0 : static_cast<int>(n) - 1;
        const int clamped = constrain(idx, 0, hi);
        gPlayback.setSongIndex(static_cast<uint8_t>(clamped));
        Serial.printf(
            "song_index=%u song_name=%s song_count=%u\n",
            gPlayback.songIndex(),
            gPlayback.songName(),
            static_cast<unsigned>(n));
        return;
    }

    if (upper.startsWith("BASE ")) {
        int r = 0;
        int g = 0;
        int b = 0;
        if (sscanf(line.c_str(), "BASE %d %d %d", &r, &g, &b) == 3) {
            setBaseColor(
                static_cast<uint8_t>(constrain(r, 0, 255)),
                static_cast<uint8_t>(constrain(g, 0, 255)),
                static_cast<uint8_t>(constrain(b, 0, 255)));
            Serial.printf("base=%d,%d,%d\n", constrain(r, 0, 255), constrain(g, 0, 255), constrain(b, 0, 255));
        }
        return;
    }

    if (upper == "STATUS") {
        Serial.printf(
            "playing=%d time_ms=%lu length_ms=%lu speed=%.2f brightness=%u mode=%d playmode=%s song_index=%u song_name=%s song_count=%u held=0x%llx req=0x%llx\n",
            gPlayback.isPlaying() ? 1 : 0,
            static_cast<unsigned long>(gPlayback.songTimeMs()),
            static_cast<unsigned long>(gPlayback.songLengthMs()),
            gPlayback.speed(),
            gCurrentBrightness,
            static_cast<int>(colorMode()),
            gPlayback.mode() == PlaybackMode::GuidedWait ? "guided" : "continuous",
            gPlayback.songIndex(),
            gPlayback.songName(),
            static_cast<unsigned>(gPlayback.songCount()),
            static_cast<unsigned long long>(gPlayback.heldMask()),
            static_cast<unsigned long long>(gPlayback.requiredMaskNow()));
        return;
    }
}

}  // namespace

void setup() {
    delay(1000);
    Serial.begin(115200);
    Serial.setTimeout(5);
    gUsbHost.begin();
    Serial.println("MIDI HOST init=1");
    gMidiIn.setHandleNoteOn(onMidiNoteOn);
    gMidiIn.setHandleNoteOff(onMidiNoteOff);
    gMidiIn.setHandleControlChange(onMidiControlChange);
    gMidiIn.setHandlePitchChange(onMidiPitchBend);

    initDisplay();
    clearPanels();
    showPanels();
    runStartupPanelTest();

    gPlayback.begin(PlaybackMode::Continuous, millis());
    gPlayback.setPlaying(false);
    setLiveFeedbackEnabled(true);
    // Switch to guided mode anytime with:
    // gPlayback.setMode(PlaybackMode::GuidedWait);
}

void loop() {
    gUsbHost.Task();
    gMidiIn.read();
    const bool hub1Attached = static_cast<bool>(gHub1);
    const bool hub2Attached = static_cast<bool>(gHub2);
    const bool midiAttached = static_cast<bool>(gMidiIn);
    if (hub1Attached != gLastHub1Attached) {
        gLastHub1Attached = hub1Attached;
        Serial.printf("USB HOST hub1=%d\n", hub1Attached ? 1 : 0);
    }
    if (hub2Attached != gLastHub2Attached) {
        gLastHub2Attached = hub2Attached;
        Serial.printf("USB HOST hub2=%d\n", hub2Attached ? 1 : 0);
    }
    if (midiAttached != gLastMidiAttached) {
        gLastMidiAttached = midiAttached;
        if (midiAttached) {
            Serial.println("MIDI HOST attached=1");
        } else {
            Serial.println("MIDI HOST attached=0");
        }
    }
    const uint32_t nowMs = millis();
    if (nowMs - gLastHostHeartbeatMs >= 2000) {
        gLastHostHeartbeatMs = nowMs;
        Serial.printf(
            "USB HOST hb hub1=%d hub2=%d midi=%d host_ms=%lu length_ms=%lu\n",
            hub1Attached ? 1 : 0,
            hub2Attached ? 1 : 0,
            midiAttached ? 1 : 0,
            static_cast<unsigned long>(nowMs),
            static_cast<unsigned long>(gPlayback.songLengthMs()));
    }

    gPlayback.update(nowMs);

    String line;
    if (readSerialLine(line)) {
        uint8_t col = 0;
        if (parseColumnLine(line, col)) {
            gPlayback.reportKeyEvent(col);
        } else {
            handleControlCommand(line);
        }
    }

    const size_t noteCount = gPlayback.collectRenderableNotes(
        gVisibleNotes, sizeof(gVisibleNotes) / sizeof(gVisibleNotes[0]));

    renderFrame(gVisibleNotes, noteCount, gPlayback.isGuidedPaused());
    delay(FRAME_DELAY_MS);
}