#pragma once

#include <stddef.h>
#include <stdint.h>

#include "playback.h"

enum class ColorMode : uint8_t {
    Fixed = 0,
    PitchClass = 1,
    Rainbow = 2,
    Alternate = 3
};

void setColorMode(ColorMode mode);
ColorMode colorMode();
void setBaseColor(uint8_t r, uint8_t g, uint8_t b);
void setLiveFeedbackEnabled(bool enabled);
bool liveFeedbackEnabled();
void pushLiveFeedback(uint8_t col, bool correct);

void renderFrame(const RenderNote *notes, size_t noteCount, bool guidedPaused);
