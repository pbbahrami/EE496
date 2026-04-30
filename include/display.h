#pragma once

#include <FastLED.h>

void initDisplay();
void setDisplayBrightness(uint8_t brightness);
void clearPanels();
void addGlobalXY(int x, int y, const CRGB &color);
void showPanels();
