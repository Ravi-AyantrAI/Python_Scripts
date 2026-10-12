# Smart PPE Testbed Firmware – Integration and Optimisation Report

This version adds the analog helmet touch sensor and its rules to the PPE firmware, then optimises the code paths that run continuously.

Every optimisation was checked against an unoptimised reference copy of the same code. The algorithms give **bit-identical results**, the phone and hub messages are **character-for-character identical**, and all PC tests pass.

> **What "measured" means here.** Speed figures were measured on a PC (GCC `-O2`), so they show relative gains, not microcontroller timings. Memory figures are `sizeof()` results. Figures marked *estimate* are calculations from the code, not measurements. Use the SystemView markers (README → *Recording and profiling with SEGGER SystemView*) and the PPK2 to measure them on the boards.

---

## 1. Summary

| # | Change | Where | Effect | Basis |
|---|---|---|---|---|
| I1 | Analog touch sensor with power-up baseline | Helmet | Worn = signal drops ≥ 30 % below the "not worn" level | 7/7 tests |
| I2 | Touch-aware on-body rules | Vest | Helmet off reported in ~3 s even when nobody moves; resting worker stays "on body" | 13/13 tests |
| O1 | Rhythm search: running energy sums | Both | 1 multiply-add per sample per shift instead of 3 | Identical results |
| O2 | Skip the rhythm search when still | Both | Motion summary **2.1× faster** on mixed activity | Measured (PC) |
| O3 | Text built only when a state changes | Vest | Decision step **28× faster** while nothing changes | Measured (PC) |
| O4 | "Moving" flag reuses the motion summary | Helmet | Removes ~20,000 float operations/s and a 400-byte buffer | Estimate / `sizeof` |
| O5 | Impact check without square root | Helmet | No `sqrtf` on the 50 Hz path | Code |
| O6 | 16-bit motion history | Both | Motion state **840 → 456 bytes** per board | `sizeof` |
| O7 | Two small stack slices instead of a 193-entry table | Both | Avoids +772 bytes of static RAM that O1 would otherwise need | Code |
| O8 | Sensor I/O outside the lock | Helmet | Lock held for one 56-byte copy, not for I2C transfers | Code |
| O9 | Lock-free hand-over at 50 Hz | Vest | Mutex operations: ~50/s → ~1/s | Code |
| O10 | Exact 50 Hz with kernel timers | Both | No sampling drift; exact 1.92 s windows | Code |
| O11 | Touch change notified at once | Helmet → vest | Vest learns of it in ~1 s, not on the next 10 s summary | Code |
| O12 | IR and touch at 25 Hz | Helmet | Half the ADC conversions | Code |
| O13 | Sensor log configurable | Helmet | `CONFIG_PPE_SENSOR_LOG_S=0` turns it off | Code |
| O14 | Helmet keeps the vest's 1 s link interval | Helmet | Stops a silent switch to 30–50 ms: about 20–33× fewer link events (*estimate*) | Config |
| O15 | One button re-measures both baselines | Helmet | IR and touch "helmet off" levels together (BTN4 held 2 s) | Code |

---

## 2. Integration: the analog touch sensor

### I1 — Helmet: baseline-relative touch detection (`common/sensors/touch_level.c`)

**Before:** a TTP223 read as a digital pin (P1.06), high meaning touched. Such modules can drop a long continuous touch when they re-calibrate.

**Now:** the sensor's signal is read as a **voltage** on P0.04 (Arduino A0, AIN0), and `touch_level.c` decides:

| Step | Behaviour |
|---|---|
| Power-up (helmet off) | Averages the signal for 2 s: this is the "not worn" baseline |
| Worn | Signal ≥ 30 % below the baseline for 200 ms |
| Removed | Signal back to within 15 % of the baseline for 200 ms. The gap between 30 and 15 % stops flicker near the threshold |
| Drift | While not worn, the baseline slowly follows temperature or humidity (time constant ~20 s) |
| Powered up while worn | When the helmet is removed, the signal rises far above the baseline; after 3 s the baseline is corrected |
| Re-measure | Hold BTN4 for 2 s with the helmet off (also re-measures the IR baseline, O15) |

An on/off module also works: that is simply a 100 % drop.

**Verified:** `tests/test_touch_level.c`, 7/7. It covers an on/off module, an analog 35 % drop, a 10 % drop (correctly ignored), 5 % drift over 60 s (no false "worn"), power-up while worn (self-corrects), a 100 ms glitch (ignored) and the hysteresis band.

### I2 — Vest: touch-aware on-body rules (`common/sensors/fusion.c`, `vest/src/onbody.c`)

The helmet's touch state reaches the vest in its status notification (`PPE_SENS_HELMET_TOUCH` + `cap_prox`), and the motion-matching rules use it:

| Situation | Before (motion only) | Now |
|---|---|---|
| Helmet put on a table, worker standing still | Not detectable; "unknown" after 60 s | **NOT on body in 3.0 s** (touch released) |
| Worker resting 90 s, helmet on | "Unknown" after 60 s | **Stays ON body**, reported as "worker resting" |
| Object pressing the touch pad, helmet on a table, worker walking | — | Motion overrules the impossible touch: NOT on body |
| Touch released while still moving in step | — | NOT on body, flagged "loose?" |

**Verified:** `tests/test_body_motion.c`, 13/13. The 8 original motion-only scenarios give identical results and timings to before.

---

## 3. Optimisations

### A. CPU time in the algorithms

**O1 — Rhythm search with running energy sums** (`motion_features.c: rhythm()`)

The step rhythm is found by autocorrelation over 36 shifts of a 192-sample history. Each shift needs a correlation sum and two energy sums for normalisation.

| | Per sample, per shift |
|---|---|
| Before | 3 multiply-adds (the energy sums were recomputed for every shift) |
| Now | 1 multiply-add; both energy sums come from one running total computed once |

The results are bit-identical over 312 windows of 10-minute mixed motion.

**O2 — Skip the rhythm search when nothing moves** (`motion_features.c: mf_add()`)

The decision logic only reads the rhythm when **both** items move (≥ 30 mg), so it is not computed below 20 mg. This covers a worker sitting or a helmet on a table, which is most of the time.

Measured over 10 minutes of walking, standing, lying on a table and carried motion:

| Data | Reference | Optimised | Speed-up |
|---|---|---|---|
| Mixed activity (300 repeats) | 0.804 s | 0.389 s | **2.1×** |
| Walking only (rhythm runs every window in both versions) | 0.806 s | 0.702 s | 1.1× |

The walking-only gain is small on a PC because the search runs once per 96 samples and the compiler already vectorises the loop. Check the real gain on the nRF chips with the SystemView marker **"On-body decision"**.

**O3 — Build message text only when something changes** (`fusion.c: fz_step()`)

**Before:** every 1.92 s while moving, the rhythm text ("rhythm 1.90/1.90 Hz, match 94%") was formatted with `snprintf`, even though a message is only sent when a state changes.

**Now:** the decision records a reason code (`enum why`), and the text is formatted only for an actual change.

Measured: 3,000,000 decision steps while walking with no change took **0.805 s before and 0.029 s after: 28× faster**. The test output (82 lines: every message and every timing) is identical to the reference. It also saves about 190 bytes of stack per step.

**O4 — Helmet "moving" flag from the motion summary** (`helmet/src/sensors.c: imu_poll()`)

**Before:** at every 50 Hz sample, a 100-sample variance was recomputed in two passes (*estimate:* ~400 float operations per sample, about 20,000 per second), using a 400-byte float buffer.

**Now:** "moving" uses the motion summary's level, which is already computed every 1.92 s (≥ 22 mg, the same threshold as before: variance 0.0005 g²). It is held for 10 s as before. The buffer and the per-sample loops are gone.

**O5 — Impact detection without a square root** (`imu_poll()`)

The 6 g impact check compares the squared magnitude with the squared threshold. `sqrtf` now runs only when an impact is actually logged.

### B. Memory

**O6 — 16-bit motion history** (`struct mf_state`)

The 3.84 s history of total acceleration is stored as `int16_t` milli-g (range ±32 g) instead of `float`. The 1 mg resolution is below anything the decisions use, and the results stay bit-identical.

**O7 — No prefix table for O1**

A straightforward version of O1 needs a 193-float (772-byte) static table. Only two slices of it are ever read (shifts 15–50), so those 72 floats are kept on the stack while the function runs.

**Memory result (`sizeof`):**

| Item | Before | After | Change |
|---|---|---|---|
| `struct mf_state` (helmet and vest, one each) | 840 B | 456 B | −384 B per board |
| Helmet "moving" buffer | 400 B | — | −400 B |
| Helmet working copy `w` (O8) | — | 56 B | +56 B |
| Touch detector state | — | 32 B | +32 B |
| **Net, helmet** | | | **≈ −696 B** |
| **Net, vest** | | | **−384 B** |

### C. Concurrency and real-time behaviour

**O8 — Helmet sensor thread: I/O outside the lock** (`helmet/src/sensors.c`)

**Before:** the thread held the snapshot mutex while it read the MPU-6050 and MAX30102 over I2C (*estimate:* 0.5–1 ms every 20 ms). The main 250 ms tick reads that snapshot from the cooperative system work queue, so the work queue could stall behind an I2C transfer.

**Now:** all reads go into a private working copy, and the shared snapshot is updated with one 56-byte copy under the lock. Readers wait microseconds at most.

**O9 — Vest: lock-free hand-over on the 50 Hz path** (`vest/src/onbody.c`)

**Before:** `onbody_sample()` took a mutex 50 times a second to check whether a helmet summary had arrived, which happens once per 1.92 s.

**Now:** it reads an atomic flag, and takes the mutex only when a summary is actually waiting, plus once per decision window for the touch state. Mutex operations drop from ~50/s to ~1/s.

**O15 — Recalibration requested, not performed, from other threads**

BTN4 (work-queue context) sets an atomic request. The sensor thread performs the recalibration at its next tick, so no other thread changes calibration state while it is in use.

### D. Timing accuracy

**O10 — Exact 50 Hz on both sampling paths** (helmet `sensors_thread`, vest `motion_thread`)

**Before:** "do the work, then `k_sleep(20 ms)`". The real period was 20 ms plus the work time (I2C, ADC, algorithms), so it ran slower than 50 Hz (*estimate:* a few percent). The algorithms assume exactly 50 Hz, so the step-rhythm estimate was biased by the same percentage, and every "1.92 s" window was longer.

**Now:** a kernel timer with `k_timer_status_sync()` gives an exact 20 ms period, independent of the work time.

The check also confirmed that neither loop contains an early `continue`. With the old sleep-at-the-bottom pattern, that would have skipped the sleep and spun the CPU.

### E. Radio and latency

**O11 — Touch changes notified immediately** (`helmet/src/main.c: sensor_status_tick()`)

**Before:** the vest saw the helmet's touch state only in the next status notification. That came on a wear-state change (3–5 s later) or with the 10 s summary.

**Now:** any change of the touch state, or of its "calibrated" status, sends a status notification at once. The vest receives it at the next connection event (≤ ~1 s at the 1 s interval).

**O14 — The helmet keeps the vest's 1 s connection interval** (`helmet/prj.conf`)

The vest sets the helmet link to a 1 s interval. Zephyr's default (`CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS=y`) makes a peripheral request its own preferred parameters, 30–50 ms by default, about 5 s after connecting, and the vest accepts.

So the link silently ran at 30–50 ms. With `CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS=n` it stays at 1 s: about 20–33× fewer connection events on both boards (*estimate*). This is likely the largest power saving in this version. Verify it with the PPK2 on a connected helmet.

### F. Power and I/O

**O12 — IR and touch at 25 Hz:** both run on every second 20 ms tick, halving ADC conversions and FIFO reads. The 200 ms touch debounce still spans 5 readings. The IMU stays at 50 Hz, as fall detection and motion matching need.

**O13 — Configurable sensor log:** `CONFIG_PPE_SENSOR_LOG_S` sets the log interval; `0` turns it off for quieter UART output and lower power. The default stays 2 s for tuning.

---

## 4. How it was verified

| Check | Result |
|---|---|
| Motion summary, reference vs optimised, 312 windows (walking, standing, table, carried) | 0 differences in rhythm, motion level, rotation, shape |
| On-body decisions, reference vs optimised, full test output | Identical (82 lines: every message, every timing) |
| `tests/test_body_motion.c` | 13 / 13 |
| `tests/test_touch_level.c` | 7 / 7 |
| `tests/test_fall_detect.c` | 8 / 8 |
| `tests/test_ppg.c` | 6 / 6 |
| Compile: helmet, vest, anchor A and B, all shared files; normal and SystemView builds; helmet with and without the touch sensor | No errors, no warnings (against stand-in Zephyr headers) |
| Hub sketch (Arduino auto-prototype emulation) | Pass |

**Not yet done:** a build against the real nRF Connect SDK and runs on the boards. Expect a first-build fix or two, especially in the new ADC devicetree entries.

---

## 5. Measuring the gains on the boards

| What | How |
|---|---|
| CPU time of one decision | SystemView marker **"On-body decision"** (vest): before/after duration |
| Sampling regularity | Gaps between **"IMU sample"** markers (vest) and **"Sensor poll"** markers (helmet): should be exactly 20 ms |
| Lock contention | SystemView thread view: the helmet's system work queue should no longer block on the sensor mutex |
| Link interval (O14) | Helmet log / sniffer: connection interval stays 1000 ms after 5 s; PPK2: connected current of both boards |
| Touch latency (O11) | Remove the helmet and time the vest's `HELMET_NOT_ON_BODY` event (~3–4 s expected) |

---

## 6. Considered but not changed

| Idea | Why not |
|---|---|
| Send motion summaries less often when still | The vest treats a summary older than 3 s as missing; the radio saving is small |
| Fixed-point arithmetic | All three chips (nRF5340, nRF54L15, nRF52840) have a hardware FPU |
| Lower IMU rate | Fall detection and rhythm detection need 50 Hz |
| Merge the status and motion notifications | 13 + 20 bytes exceeds one notification at the default MTU; needs an MTU exchange |
| The vest's 50 % scanning while linked | Still its largest power cost, but changing it is an architecture change (short scan windows or periodic advertising). See the reconnect lab |

---

## 7. Files changed

| File | Change |
|---|---|
| `common/sensors/touch_level.c/.h` | **New:** baseline-relative touch detector (I1) |
| `common/sensors/fusion.c/.h` | Touch-aware rules (I2); text built only on change (O3) |
| `common/sensors/motion_features.c/.h` | O1, O2, O6, O7 |
| `helmet/src/sensors.c/.h` | Analog touch (I1); O4, O5, O8, O10, O12, O15 |
| `helmet/src/main.c` | Immediate touch notification (O11); configurable log (O13); combined recalibration (O15) |
| `helmet/Kconfig`, `prj.conf`, `CMakeLists.txt`, board overlay | Touch options, `CONFIG_ADC=y`, O14, ADC channel AIN0 on P0.04 |
| `vest/src/onbody.c/.h` | Touch input (I2); lock-free hand-over (O9) |
| `vest/src/motion.c` | Exact 50 Hz (O10) |
| `vest/src/main.c` | Passes the helmet touch state to the on-body logic |
| `vest/Kconfig` | `CONFIG_PPE_BM_TOUCH_ON_MS`, `CONFIG_PPE_BM_TOUCH_OFF_S` |
| `tests/test_body_motion.c`, `tests/test_touch_level.c`, `tests/sim_motion.c/.h` | Tests for all of the above |
| `README.md` | Touch wiring, calibration, rules and troubleshooting |

**Reflash:** helmet and vest. The anchors and hub are unchanged by this version.
