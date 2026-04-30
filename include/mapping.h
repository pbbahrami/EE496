#pragma once

#include <stdint.h>

int localXYToIndex(int x, int y);
bool globalToPanel(int globalX, int globalY, uint8_t &panelIndex, int &localX, int &localY);
