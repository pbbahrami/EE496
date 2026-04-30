#include "mapping.h"

#include "config.h"

int localXYToIndex(int x, int y) {
    if (x < 0 || x >= PANEL_WIDTH || y < 0 || y >= PANEL_HEIGHT) {
        return -1;
    }

    // Columns are wired/indexed increasing left -> right on each PCB panel.
    if ((x % 2) == 0) {
        return x * PANEL_HEIGHT + y;
    }
    return x * PANEL_HEIGHT + (PANEL_HEIGHT - 1 - y);
}

bool globalToPanel(int globalX, int globalY, uint8_t &panelIndex, int &localX, int &localY) {
    if (globalX < 0 || globalX >= TOTAL_WIDTH || globalY < 0 || globalY >= TOTAL_HEIGHT) {
        return false;
    }

    panelIndex = static_cast<uint8_t>(globalX / PANEL_WIDTH);
    localX = globalX % PANEL_WIDTH;
    localY = globalY;
    return true;
}
