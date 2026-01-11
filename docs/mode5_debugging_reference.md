# Mode 5 (PHASE_IQ) Debugging Reference

## Scope
This document summarizes the current state of Chirp mode 5 (PHASE_IQ), observed failures, fixes attempted, and recommended future directions. Mode 5 is intended to emit both TLV 0x0520 (phase output) and TLV 0x0500 (complex range FFT) so the dashboard can render I/Q-derived range profiles while preserving vitals extraction.

## Current Behavior
- Mode 3 (PHASE) streams reliably and produces vitals.
- Mode 5 (PHASE_IQ) has historically stopped streaming after 1–2 frames.
- Recent firmware changes introduced extensive debug logging and a temporary disable of complex FFT output in some builds, which invalidates mode‑5 tests.

## What’s Been Tried
### 1) Added PHASE_IQ output mode (mode 5)
- Code change: `Chirp_shouldOutputTLV()` now enables TLV 0x0500 and 0x0520 when mode == 5.
- Result: mode 5 can request both TLVs, but streaming stability was not resolved by this change alone.

### 2) Increased TLV header array size
- The UART output path stores TLV headers in a fixed array: `MmwDemo_output_message_tl tl[]`.
- It previously used `MMWDEMO_OUTPUT_MSG_MAX` (10), but mode 5 can produce up to ~12–14 TLVs in one frame (standard TI TLVs + chirp TLVs).
- Fix means switching to a larger buffer: `MMWDEMO_OUTPUT_MSG_TL_ARRAY_SIZE 16`.
- This is the most plausible root-cause fix for the “1–2 frames then die” symptom.

### 3) Added debug logging and version markers
- One‑shot TLV count and packet length logs were added to confirm the number of TLVs and packet size.
- Firmware version was bumped to help confirm the build deployed to hardware.
- Risk: excessive UART logging can disrupt streaming.

### 4) Temporary debug changes (not stable for validation)
- Complex FFT output was disabled in one build by removing `MMWDEMO_OUTPUT_COMPLEX_RANGE_FFT_ENABLE`.
- A static `complexFftBuffer[256]` copy was added before UART transmit to avoid L3 overwrite during blocking writes.
- These changes can mask real issues or invalidate mode‑5 tests if not reverted or documented.

## Likely Root Cause
- **High confidence:** TLV header array overflow in `MmwDemo_transmitProcessedOutput` when too many TLVs are emitted. This would corrupt stack state and kill the stream after 1–2 frames.
- **Medium confidence:** UART throughput and blocking writes may expose a race with L3 radarCube data (leading to corrupted TLVs), especially when complex FFT output is enabled.

## Validation Checklist (for Future Mode‑5 Work)
1. **Confirm correct firmware build is flashed.**
   - Use a version string in `chirp status` or a known build marker.
2. **Ensure Complex FFT output is enabled.**
   - `MMWDEMO_OUTPUT_COMPLEX_RANGE_FFT_ENABLE` must be defined in the build.
3. **Log TLV counts once per session.**
   - Validate `header.numTLVs` stays ≤ 16.
4. **Verify mode‑5 stability on hardware.**
   - Stream for ≥60 seconds without frame drops or UART lockups.

## Open Questions
- Is the L3 radar cube being overwritten during UART transmission, causing corrupted complex FFT TLVs?
- Are there other fixed-size buffers (besides TLV header array) that assume ≤10 TLVs?
- Is UART throughput sufficient at the current baud rate when complex FFT is included?

## Suggested Future Directions
1. **Keep mode 3 as default until downstream pipelines are stable.**
2. **Re‑enable mode 5 with minimal debug logging** and confirm TLV count is within bounds.
3. **Validate complex FFT integrity** by comparing packet lengths and CRC (if added) across frames.
4. **If needed, switch to DMA-based UART output** or reduce payload size (subsample bins or lower FPS).

## Decision
Mode 5 work is deferred until downstream pipeline and vitals stability are validated under mode 3. The above checklist should be used when resuming mode 5 debugging.
