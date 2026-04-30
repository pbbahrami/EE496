#pragma once

#include <stddef.h>
#include <stdint.h>

enum class PlaybackMode : uint8_t {
    Continuous = 0,
    GuidedWait = 1
};

struct RenderNote {
    uint8_t col;
    uint8_t midiNote;
    uint16_t seqIndex;
    uint8_t altParity;
    float headY;
    float tailY;
    bool awaitingStrike;
};

class PlaybackEngine {
public:
    void begin(PlaybackMode mode, uint32_t nowMs);
    void setMode(PlaybackMode mode);
    PlaybackMode mode() const;

    void update(uint32_t nowMs);
    bool reportKeyDown(uint8_t col);
    bool reportKeyUp(uint8_t col);
    bool reportKeyEvent(uint8_t col);
    void setSpeed(float speed);
    float speed() const;
    void setPlaying(bool playing);
    bool isPlaying() const;
    void resetSongTime();
    void seekToMs(uint32_t targetMs);
    uint32_t songLengthMs() const;
    void setSongIndex(uint8_t index);
    uint8_t songIndex() const;
    uint8_t songCount() const;
    const char *songName() const;
    uint64_t heldMask() const;
    uint64_t requiredMaskNow() const;

    size_t collectRenderableNotes(RenderNote *out, size_t maxCount) const;

    bool isGuidedPaused() const;
    uint32_t songTimeMs() const;

private:
    uint64_t requiredMaskAt(uint32_t timeMs) const;
    bool guidedCanAdvanceAt(uint32_t timeMs) const;

    PlaybackMode mode_ = PlaybackMode::Continuous;
    uint32_t songTimeMs_ = 0;
    uint32_t lastUpdateMs_ = 0;
    bool guidedPaused_ = false;
    float speed_ = 1.0f;
    bool playing_ = true;
    uint64_t heldMask_ = 0;
    bool seekActive_ = false;
    uint32_t seekTargetMs_ = 0;
    uint8_t songIndex_ = 0;
};
