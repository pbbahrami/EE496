#include "renderer.h"

#include <math.h>

#include <FastLED.h>

#include "config.h"
#include "display.h"

namespace {
constexpr int STRIKE_LINE_Y = TOTAL_HEIGHT - 2;
ColorMode gColorMode = ColorMode::Fixed;
CRGB gBaseColor = CRGB(32, 110, 230);
bool gLiveFeedbackEnabled = false;
uint32_t gFeedbackUntilMs[TOTAL_WIDTH] = {0};
bool gFeedbackCorrect[TOTAL_WIDTH] = {false};

float overlapAmount(float a0, float a1, float b0, float b1) {
    const float lo = fmaxf(a0, b0);
    const float hi = fminf(a1, b1);
    return fmaxf(0.0f, hi - lo);
}

uint8_t noteBrightnessAt(int y, float headY, float tailY, bool awaitingStrike) {
    const float px0 = static_cast<float>(y) - 0.5f;
    const float px1 = static_cast<float>(y) + 0.5f;

    // Fractional coverage keeps movement smooth while preserving a solid bar look.
    const float body = overlapAmount(px0, px1, tailY, headY);
    float intensity = body * 185.0f;
    if (awaitingStrike) {
        intensity *= 1.12f;
    }

    if (intensity > 255.0f) {
        intensity = 255.0f;
    }
    return static_cast<uint8_t>(intensity);
}

CRGB colorForNote(const RenderNote &n, uint8_t b) {
    CRGB c = gBaseColor;
    switch (gColorMode) {
        case ColorMode::PitchClass: {
            static const CRGB kPitchColors[12] = {
                CRGB::Blue,    CRGB(90, 0, 170), CRGB::Cyan,    CRGB::Green,
                CRGB(160, 255, 40),               CRGB::Yellow,  CRGB::Orange, CRGB(255, 80, 0),
                CRGB::Red,     CRGB(255, 0, 120), CRGB::Magenta, CRGB(180, 80, 255)};
            c = kPitchColors[n.midiNote % 12];
            break;
        }
        case ColorMode::Rainbow:
            c = CHSV(static_cast<uint8_t>((n.midiNote * 17) & 0xFF), 255, 255);
            break;
        case ColorMode::Alternate:
            c = (n.altParity == 0) ? CRGB(32, 170, 255) : CRGB(255, 115, 20);
            break;
        case ColorMode::Fixed:
        default:
            break;
    }

    c.nscale8_video(b);
    if (n.awaitingStrike) {
        c += CRGB(20, 10, 0);
    }
    return c;
}

void drawStrikeLine(bool guidedPaused) {
    const CRGB strikeColor = guidedPaused ? CRGB(24, 24, 4) : CRGB(3, 3, 8);
    for (int x = 0; x < TOTAL_WIDTH; ++x) {
        addGlobalXY(x, STRIKE_LINE_Y, strikeColor);
    }
}

void drawPanelDividers() {
    for (int k = 1; k < NUM_PANELS; ++k) {
        const int x = k * PANEL_WIDTH - 1;
        for (int y = 0; y < TOTAL_HEIGHT; ++y) {
            addGlobalXY(x, y, CRGB(8, 0, 0));
        }
    }
}
}  // namespace

void setColorMode(ColorMode mode) {
    gColorMode = mode;
}

ColorMode colorMode() {
    return gColorMode;
}

void setBaseColor(uint8_t r, uint8_t g, uint8_t b) {
    gBaseColor = CRGB(r, g, b);
}

void setLiveFeedbackEnabled(bool enabled) {
    gLiveFeedbackEnabled = enabled;
}

bool liveFeedbackEnabled() {
    return gLiveFeedbackEnabled;
}

void pushLiveFeedback(uint8_t col, bool correct) {
    if (col >= TOTAL_WIDTH) {
        return;
    }
    gFeedbackCorrect[col] = correct;
    gFeedbackUntilMs[col] = millis() + 220;
}

void renderFrame(const RenderNote *notes, size_t noteCount, bool guidedPaused) {
    clearPanels();

    for (size_t i = 0; i < noteCount; ++i) {
        const RenderNote &n = notes[i];
        if (n.col >= TOTAL_WIDTH) {
            continue;
        }

        for (int y = 0; y < TOTAL_HEIGHT; ++y) {
            const uint8_t b = noteBrightnessAt(y, n.headY, n.tailY, n.awaitingStrike);
            if (b == 0) {
                continue;
            }

            CRGB c = colorForNote(n, b);
            addGlobalXY(static_cast<int>(n.col), y, c);
        }
    }

    if (SHOW_STRIKE_LINE) {
        drawStrikeLine(guidedPaused);
    }
    if (SHOW_PANEL_DIVIDERS) {
        drawPanelDividers();
    }
    if (gLiveFeedbackEnabled) {
        const uint32_t now = millis();
        for (int x = 0; x < TOTAL_WIDTH; ++x) {
            if (gFeedbackUntilMs[x] > now) {
                // Keep hit feedback at full color intensity for maximum visibility.
                const CRGB mark = gFeedbackCorrect[x] ? CRGB::Green : CRGB::Red;
                addGlobalXY(x, STRIKE_LINE_Y, mark);
            }
        }
    }
    showPanels();
}
