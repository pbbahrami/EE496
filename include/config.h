#pragma once

#include <stdint.h>

static constexpr int NUM_PANELS = 5;

// One NeoPixel data pin per panel (left → right). Matches OctoWS2811 / RJ45 mapping:
// Cable 1 (first jack): strips 1–4 → pins 2, 14, 7, 8
// Cable 2 (second jack): strip 5 → pin 6 (Orange / White-Orange pair)
static constexpr uint8_t PANEL_PINS[NUM_PANELS] = {2, 14, 7, 8, 6};

static constexpr int PANEL_WIDTH = 12;
static constexpr int PANEL_HEIGHT = 24;
static constexpr int PANEL_LEDS = PANEL_WIDTH * PANEL_HEIGHT;

static constexpr int TOTAL_WIDTH = PANEL_WIDTH * NUM_PANELS;
static constexpr int TOTAL_HEIGHT = PANEL_HEIGHT;

static constexpr uint8_t BRIGHTNESS = 35;
static constexpr uint32_t FRAME_DELAY_MS = 12;

// Visual guides used during development; disable for clean playback.
static constexpr bool SHOW_STRIKE_LINE = false;
static constexpr bool SHOW_PANEL_DIVIDERS = false;
