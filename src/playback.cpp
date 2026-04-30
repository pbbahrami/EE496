#include "playback.h"

#include "config.h"
#include "song_catalog_data.h"

namespace {
constexpr int STRIKE_LINE_Y = TOTAL_HEIGHT - 2;
constexpr float MS_PER_PIXEL = 110.0f;
constexpr float PRESPAWN_MARGIN_PX = 6.0f;
constexpr float SEEK_SPEED_MULT = 3.5f;
}

void PlaybackEngine::begin(PlaybackMode mode, uint32_t nowMs) {
    mode_ = mode;
    songTimeMs_ = 0;
    lastUpdateMs_ = nowMs;
    guidedPaused_ = false;
    playing_ = true;
    heldMask_ = 0;
    seekActive_ = false;
    seekTargetMs_ = 0;
}

void PlaybackEngine::setMode(PlaybackMode mode) {
    mode_ = mode;
    if (mode_ == PlaybackMode::Continuous) {
        guidedPaused_ = false;
    }
}

PlaybackMode PlaybackEngine::mode() const {
    return mode_;
}

void PlaybackEngine::update(uint32_t nowMs) {
    const uint32_t elapsedMs = nowMs - lastUpdateMs_;
    lastUpdateMs_ = nowMs;
    const uint32_t scaledElapsed = static_cast<uint32_t>(static_cast<float>(elapsedMs) * speed_);
    if (scaledElapsed == 0 && !seekActive_) {
        return;
    }

    if (seekActive_) {
        const uint32_t seekStep = static_cast<uint32_t>(static_cast<float>(elapsedMs) * SEEK_SPEED_MULT);
        const uint32_t step = seekStep > 0 ? seekStep : 1;
        if (songTimeMs_ < seekTargetMs_) {
            songTimeMs_ = (songTimeMs_ + step >= seekTargetMs_) ? seekTargetMs_ : (songTimeMs_ + step);
        } else if (songTimeMs_ > seekTargetMs_) {
            songTimeMs_ = (songTimeMs_ <= seekTargetMs_ + step) ? seekTargetMs_ : (songTimeMs_ - step);
        }
        if (songTimeMs_ == seekTargetMs_) {
            seekActive_ = false;
        }
    }

    if (!playing_) {
        return;
    }

    if (mode_ == PlaybackMode::GuidedWait) {
        const bool canAdvance = guidedCanAdvanceAt(songTimeMs_);
        guidedPaused_ = !canAdvance;
        if (!canAdvance) {
            return;
        }
    } else {
        guidedPaused_ = false;
    }

    songTimeMs_ += scaledElapsed;
}

bool PlaybackEngine::reportKeyDown(uint8_t col) {
    if (col >= TOTAL_WIDTH) {
        return false;
    }
    heldMask_ |= (uint64_t{1} << col);
    if (mode_ != PlaybackMode::GuidedWait) {
        return true;
    }
    if (!guidedPaused_) {
        return true;
    }
    if (!guidedCanAdvanceAt(songTimeMs_)) {
        return false;
    }
    guidedPaused_ = false;
    return true;
}

bool PlaybackEngine::reportKeyUp(uint8_t col) {
    if (col >= TOTAL_WIDTH) {
        return false;
    }
    heldMask_ &= ~(uint64_t{1} << col);
    return true;
}

bool PlaybackEngine::reportKeyEvent(uint8_t col) {
    return reportKeyDown(col);
}

void PlaybackEngine::setSpeed(float speed) {
    if (speed < 0.2f) {
        speed = 0.2f;
    }
    if (speed > 3.0f) {
        speed = 3.0f;
    }
    speed_ = speed;
}

float PlaybackEngine::speed() const {
    return speed_;
}

void PlaybackEngine::setPlaying(bool playing) {
    playing_ = playing;
}

bool PlaybackEngine::isPlaying() const {
    return playing_;
}

void PlaybackEngine::resetSongTime() {
    songTimeMs_ = 0;
    guidedPaused_ = false;
    heldMask_ = 0;
    seekActive_ = false;
    seekTargetMs_ = 0;
}

void PlaybackEngine::seekToMs(uint32_t targetMs) {
    const uint32_t len = songLengthMs();
    seekTargetMs_ = targetMs > len ? len : targetMs;
    seekActive_ = true;
}

uint32_t PlaybackEngine::songLengthMs() const {
    const SongDef &song = kSongs[songIndex_];
    const NoteEvent &last = song.events[song.count - 1];
    return last.startMs + last.durationMs;
}

void PlaybackEngine::setSongIndex(uint8_t index) {
    if (index >= kSongCount) {
        return;
    }
    songIndex_ = index;
    resetSongTime();
}

uint8_t PlaybackEngine::songIndex() const {
    return songIndex_;
}

uint8_t PlaybackEngine::songCount() const {
    return kSongCount;
}

const char *PlaybackEngine::songName() const {
    return kSongs[songIndex_].name;
}

uint64_t PlaybackEngine::heldMask() const {
    return heldMask_;
}

uint64_t PlaybackEngine::requiredMaskNow() const {
    return requiredMaskAt(songTimeMs_);
}

size_t PlaybackEngine::collectRenderableNotes(RenderNote *out, size_t maxCount) const {
    if (out == nullptr || maxCount == 0) {
        return 0;
    }

    const SongDef &song = kSongs[songIndex_];
    size_t count = 0;
    uint16_t colOrdinal[TOTAL_WIDTH] = {0};
    for (size_t i = 0; i < song.count && count < maxCount; ++i) {
        const NoteEvent &note = song.events[i];
        uint8_t altParity = 0;
        if (note.col < TOTAL_WIDTH) {
            altParity = static_cast<uint8_t>(colOrdinal[note.col] & 1u);
            colOrdinal[note.col]++;
        }
        const float deltaMs = static_cast<float>(note.startMs) - static_cast<float>(songTimeMs_);
        const float headY = static_cast<float>(STRIKE_LINE_Y) - (deltaMs / MS_PER_PIXEL);

        const float noteLengthPx = static_cast<float>(note.durationMs) / MS_PER_PIXEL;
        const float tailY = headY - noteLengthPx;

        if (headY < -PRESPAWN_MARGIN_PX) {
            continue;
        }
        if (tailY > static_cast<float>(TOTAL_HEIGHT + PRESPAWN_MARGIN_PX)) {
            continue;
        }

        if (mode_ == PlaybackMode::GuidedWait &&
            songTimeMs_ >= (note.startMs + note.durationMs)) {
            // In guided mode, drop completed notes immediately to reduce visual ambiguity.
            continue;
        }

        out[count].col = note.col;
        out[count].midiNote = note.midiNote;
        out[count].seqIndex = static_cast<uint16_t>(i & 0xFFFF);
        out[count].altParity = altParity;
        out[count].headY = headY;
        out[count].tailY = tailY;
        const bool activeAtNow = (songTimeMs_ >= note.startMs) &&
                                 (songTimeMs_ < (note.startMs + note.durationMs));
        const bool held = ((heldMask_ >> note.col) & uint64_t{1}) != 0;
        out[count].awaitingStrike = (mode_ == PlaybackMode::GuidedWait) && activeAtNow && !held;
        ++count;
    }
    return count;
}

bool PlaybackEngine::isGuidedPaused() const {
    return guidedPaused_;
}

uint32_t PlaybackEngine::songTimeMs() const {
    return songTimeMs_;
}

uint64_t PlaybackEngine::requiredMaskAt(uint32_t timeMs) const {
    const SongDef &song = kSongs[songIndex_];
    uint64_t mask = 0;
    for (size_t i = 0; i < song.count; ++i) {
        const NoteEvent &ev = song.events[i];
        const uint32_t endMs = ev.startMs + ev.durationMs;
        if (ev.startMs <= timeMs && timeMs < endMs && ev.col < TOTAL_WIDTH) {
            mask |= (uint64_t{1} << ev.col);
        }
        if (ev.startMs > timeMs && mask != 0) {
            // Events are sorted; once we're past active window start and found notes, we can stop.
            break;
        }
    }
    return mask;
}

bool PlaybackEngine::guidedCanAdvanceAt(uint32_t timeMs) const {
    const uint64_t required = requiredMaskAt(timeMs);
    if (required == 0) {
        return true;
    }
    return (heldMask_ & required) == required;
}
