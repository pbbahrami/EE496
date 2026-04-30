#include "display.h"

#include "config.h"
#include "mapping.h"

namespace {
CRGB ledsPanels[NUM_PANELS][PANEL_LEDS];
}

void initDisplay() {
    // Template pin must be compile-time constant per strip (indices match PANEL_PINS).
    FastLED.addLeds<NEOPIXEL, PANEL_PINS[0]>(ledsPanels[0], PANEL_LEDS);
    FastLED.addLeds<NEOPIXEL, PANEL_PINS[1]>(ledsPanels[1], PANEL_LEDS);
    FastLED.addLeds<NEOPIXEL, PANEL_PINS[2]>(ledsPanels[2], PANEL_LEDS);
    FastLED.addLeds<NEOPIXEL, PANEL_PINS[3]>(ledsPanels[3], PANEL_LEDS);
    FastLED.addLeds<NEOPIXEL, PANEL_PINS[4]>(ledsPanels[4], PANEL_LEDS);
    FastLED.setBrightness(BRIGHTNESS);
}

void setDisplayBrightness(uint8_t brightness) {
    FastLED.setBrightness(brightness);
}

void clearPanels() {
    for (int p = 0; p < NUM_PANELS; ++p) {
        fill_solid(ledsPanels[p], PANEL_LEDS, CRGB::Black);
    }
}

void addGlobalXY(int x, int y, const CRGB &color) {
    uint8_t panelIndex = 0;
    int localX = 0;
    int localY = 0;
    if (!globalToPanel(x, y, panelIndex, localX, localY)) {
        return;
    }

    const int index = localXYToIndex(localX, localY);
    if (index < 0) {
        return;
    }

    ledsPanels[panelIndex][index] += color;
}

void showPanels() {
    FastLED.show();
}
