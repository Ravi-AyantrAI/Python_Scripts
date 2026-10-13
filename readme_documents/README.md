# Body-motion lab: "is the helmet / vest on the body?" from motion alone

Both boards are **nRF52840 DKs**, each with an MPU-6050. The **helmet** board summarises its motion every 2 s and broadcasts it. The **vest** board compares that with its own motion and sends plain-text messages to your **phone**, such as:

```text
[00:04] Connected to PPE-VEST kit 5. Messages follow; send 's' for status.
[00:08] Helmet ON body (rhythm 1.90/1.90 Hz, match 94%)
[00:08] Vest ON body (rhythm 1.90/1.90 Hz, match 94%)
[01:12] Helmet NOT on body (still 11s while vest moves)
[02:40] Helmet moving, NOT worn? (rotating 150 deg/s: carried?)
[04:05] Both still for 61 s: worker resting or kit put down
[05:30] Helmet signal LOST (no data for 11 s)
[06:10] Helmet NOT on body (touch sensor released)
[07:45] Both still for 61 s; helmet touch says worn: worker resting
[00:30] Helmet ON body | Vest ON body | H 131mg 1.90Hz 28dps | V 220mg 1.90Hz | match 96%
```

> **Status.** The decision logic passes 23 of 23 scenarios (8 motion-only, 5 with the touch sensor, 10 with barometers), the touch detector 7 of 7 and the BMP581 driver 8 of 8, in PC tests that run exactly the code on the boards. The firmware compiles cleanly against stand-in Zephyr headers but has **not yet been built against your SDK or run on boards**. Expect a first-build fix or two.

---

## How it decides

Every 1.92 s each board computes, from 50 Hz accelerometer + gyro data:

| Feature | Meaning |
|---|---|
| **Motion** (mg) | How much it is moving: the spread of the total acceleration |
| **Rhythm** (Hz) | Its dominant beat, such as footsteps (about 1.6–2.2 Hz when walking) |
| **Rotation** (°/s) | How fast it turns. The gyro's own offset is removed |
| **Shape** (16 values) | The motion over time, used to check the two items move *together* |

Then the vest applies these rules (thresholds are Kconfig options):

| Situation | Message |
|---|---|
| Vest moving, helmet **still** for 10 s | **Helmet NOT on body** |
| Helmet moving, vest **still** for 10 s | **Vest NOT on body** |
| Both moving with the same rhythm, or shapes matching ≥ 50 % | **Helmet ON body / Vest ON body** |
| Both moving, but the helmet **rotating > 80 °/s** for 10 s | **Helmet moving, NOT worn?** (carried by the strap) |
| Both moving, but different rhythm and shape for 10 s | **Helmet moving, NOT worn?** |
| Both still for 60 s | **Both still: worker resting or kit put down** (can't tell from motion) |
| Some motion, but in between "still" and "moving" | No change: the last decision is kept |

**With the helmet touch sensor** (see Step 1), these rules come first:

| Situation | Message |
|---|---|
| Touch sensor released for 3 s | **Helmet NOT on body (touch sensor released)**, within about 3–5 s, even if nobody moves |
| Touch sensor worn for 1 s | **Helmet ON body (touch sensor worn)** |
| Touch says worn, but the helmet is still while the vest walks | **Helmet NOT on body (… touch says worn - check sensor)**: motion overrules an impossible touch |
| Touch says worn, but the helmet swings like a carried helmet | **Helmet moving, NOT worn?**: motion overrules the touch |
| Both still for 60 s while touch says worn | **Worker resting**: the helmet stays ON body |
| Touch released while the helmet still moves with the vest | **Helmet NOT on body (… loose?)**: helmet tipped back or loose |

**With a BMP581 barometer on both boards**, the vest also knows the helmet's height above it. Two sensors can disagree by up to ±30 Pa each (about ±2.5 m), so the vest first **learns** the "worn" height difference while you walk with both on. The phone then says *Barometers calibrated while worn (raw difference … cm, includes sensor offsets)*. After that:

| Situation | Message |
|---|---|
| Helmet still and ≥ 70 cm lower than when worn, for 10 s | **Helmet NOT on body (still and … cm lower than when worn)**: e.g. on a table while you stand still. Motion alone could not decide this |
| Both moving, helmet ≥ 70 cm lower than when worn, for 10 s | **Helmet moving, NOT worn? (… carried?)**: carried at hand height |
| Vest still, helmet ≥ 70 cm higher above it than when worn, for 10 s | **Vest NOT on body (… put down?)**: e.g. vest on a chair while the helmet is worn |
| Both still for 60 s, height difference as when worn | **Worker resting**, instead of "unknown" |
| The barometer contradicts a touch sensor that says "worn" (helmet on a table, pad pressed) | The barometer wins |

Stairs, lifts and weather change both pressures at once, so they cancel out. Sitting and lying down keep the head near or above the chest, so they don't trigger.

| No helmet data for 10 s | **Helmet signal LOST** |

**Why the gyro:** a helmet carried by its strap behaves like a pendulum. Its accelerometer still beats in time with your steps (it showed a 96 % match in the PC test), so rhythm alone would wrongly say "worn". But it **rotates** at about 150 °/s, against about 15–30 °/s on a head. Only the gyro sees that.

---

## Step 1 — Wire the sensors

Both boards are wired the same way, to the Arduino I2C pins of the nRF52840 DK. The DK runs its I/O at about 3 V, so the GY-521 connects directly; no voltage setting is needed.

| MPU-6050 (GY-521) | nRF52840 DK (helmet and vest) |
|---|---|
| VCC | VDD |
| GND | GND |
| SDA | P0.26 (Arduino SDA) |
| SCL | P0.27 (Arduino SCL) |
| AD0 | Open or GND (address 0x68) |

**Label the two DKs** "HELMET" and "VEST" and note their serial numbers (`nrfutil device list`). The serial number decides which firmware each board gets. If these are the DKs you used as PPE anchors, flashing replaces the anchor firmware; reflash it later with `build_all.ps1`.

**Tape each MPU-6050 firmly to its DK** (or to the helmet / vest), so they move as one.

**Helmet touch sensor (3-pin module):**

| Touch module | Helmet nRF52840 DK |
|---|---|
| VCC | VDD |
| GND | GND |
| Signal | **P0.03** (Arduino A0, analog input AIN1) |

The signal is read as a **voltage**. The firmware assumes it **drops when the helmet is worn** and rises again when it is removed, as you described:

1. **Power up the helmet NOT worn.** For the first 2 s it measures the "not worn" level (the baseline) and logs it.
2. A drop of **30 %** or more below the baseline, held for 200 ms, means **worn**. A return to within **15 %** of it means **removed**. The gap between the two stops flicker near the threshold.
3. While the helmet is off, the baseline slowly follows drift (temperature, humidity).
4. If you powered up while wearing it, the signal rises well above the baseline once you take it off. After 3 s the firmware corrects the baseline by itself.
5. **Re-measure the baseline at any time:** take the helmet off and hold **Button 1 for 2 s**.

The helmet log shows the numbers every 2 s, for example `touch: 1310 mV, baseline 2020 mV, drop 35 % -> WORN`. A module that only switches fully high or low also works: that is simply a 100 % drop. If you have no touch sensor wired, set `CONFIG_BM_HELMET_TOUCH=n` in `helmet_motion/prj.conf`.

**BMP581 barometer (7Semi breakout), one on each board.** It shares the I2C bus with the MPU-6050 (addresses 0x47 and 0x68 don't clash):

| BMP581 breakout | nRF52840 DK (helmet and vest) |
|---|---|
| VCC / 3V3 | VDD |
| GND | GND |
| SDA | P0.26 |
| SCL | P0.27 |

- The driver finds the sensor at **0x47** or **0x46** by itself. The boot log says which, for example `BMP581 found at 0x47 (chip ID 0x50)`.
- The BMP581 chip runs from 1.7–3.6 V, so the DK's ~3 V is fine. Check your board's markings: if it has a 3.3 V regulator, ~3 V in still gives the chip enough.
- Mount it with its small vent hole uncovered, out of direct wind and sun. Don't tape over it.
- Without a BMP581 on either board, the height check simply stays off. You can also set `CONFIG_BM_BARO=n`.

**No second MPU-6050 yet?** A board without a sensor **simulates** its motion, and the buttons choose what it simulates (see Step 4). So you can test with one sensor, or none.

## Step 2 — Build and flash

From the nRF Connect terminal:

```powershell
cd <unzipped folder>\body_motion_lab
powershell -ExecutionPolicy Bypass -File .\build.ps1 -Flash -SnHelmet <HELMET DK serial> -SnVest <VEST DK serial>
```

## Step 3 — Connect your phone

Use either app:

- **nRF Toolbox** (Android/iOS) → **UART** → connect to **PPE-VEST**. Messages appear as text. Type `s` and send it to get a status line at any time.
- **nRF Connect for Mobile:**
  1. Connect to **PPE-VEST** and open **Nordic UART Service**.
  2. On the **TX** characteristic (`6E400003…`), enable notifications. Each message appears as a value; switch the display to text (UTF-8) if it shows hex.
  3. To request status, write `s` as text to the **RX** characteristic (`6E400002…`).

On the vest, LED3 lights when the phone is connected, and LED4 flashes with each message.

## Step 4 — Walk-around tests

Power both DKs from **USB power banks**, so you can move around with them: helmet DK in or on a helmet or cap, vest DK in a pocket or on a vest. Keep the phone in your hand.

| # | What you do | Expected on the phone | About |
|---|---|---|---|
| 1 | Walk normally for 30 s, both items worn | `Helmet ON body`, `Vest ON body` | 4–8 s |
| 2 | Put the helmet on a table, keep walking | `Helmet NOT on body (still … while vest moves)` | 12–16 s |
| 3 | Put the helmet back on, walk | `Helmet ON body` | 4–8 s |
| 4 | Carry the helmet by its strap while walking | `Helmet moving, NOT worn? (rotating … deg/s)` | 12–16 s |
| 5 | Take the vest off and put it on a chair, keep walking with the helmet on | `Vest NOT on body` | 12–16 s |
| 6 | Stand still, both worn, for 30 s | **No message.** States stay ON | — |
| T1 | Power the helmet up with the helmet **off**, then put it on | Helmet log: `touch: baseline … mV`, then `touch: WORN`; phone: `Helmet ON body (touch sensor worn)` | 2 s, then ~2 s |
| T2 | Stand still, then put the helmet on a table (you keep standing) | `Helmet NOT on body (touch sensor released)` | 3–5 s |
| T3 | Sit still for 70 s with the helmet on | `Both still … helmet touch says worn: worker resting` (no "unknown") | 60–65 s |
| T4 | Press the touch pad with your hand while the helmet lies on a table and you walk | `Helmet NOT on body (… touch says worn - check sensor)` | 12–16 s |
| B1 | With both barometers fitted, walk 30 s with both on | `Barometers calibrated while worn (…)` | ~8 s |
| B2 | Then put the helmet on a table and **stand still** | `Helmet NOT on body (still and … cm lower than when worn)` | 12–16 s |
| B3 | Put the helmet back on, walk 10 s, then sit still for 70 s | `Both still … height above vest as when worn: worker resting` | 60–65 s |
| B4 | Walk, then hang the vest on a chair and stand still with the helmet on | `Vest NOT on body (still, helmet … cm higher above it …)` | 12–16 s |
| B5 | Walk up and down a flight of stairs | **No message.** States stay ON | — |
| 7 | Put both on the table for 70 s | `Both still for 61 s …` | 60–65 s |
| 8 | Walk the helmet out of radio range, or switch its DK off | `Helmet signal LOST` | 10–12 s |

**Simulation instead of a sensor:**

| Board | Button 1 | Button 2 | Button 3 | Button 4 |
|---|---|---|---|---|
| Helmet | Walking | On table | Carried by strap | Standing |
| Vest | Walking | On chair | Standing | Send status now |

For example, set both to walking, then press the helmet's Button 2: about 12–16 s later the phone says *Helmet NOT on body*. The helmet log says when it is simulating.

**LEDs:** on the helmet, LED1 = moving, LED2 = still, LED3 toggles with each broadcast summary, LED4 = touch sensor says worn. On the vest, LED1 = helmet on body, LED2 = vest on body, LED3 = phone connected, LED4 = message sent.

## Step 5 — Tune with the status lines

Every 30 s (and when you send `s`) the vest sends something like:

```text
Helmet ON body | Vest ON body | H 131mg 1.90Hz 28dps | V 220mg 1.90Hz | match 96%
```

Note these numbers in each situation, then adjust the Kconfig options in `vest_motion/prj.conf` (for example `CONFIG_BM_SWING_DPS=100`) and rebuild the vest:

| Option | Default | Tune it if… |
|---|---|---|
| `CONFIG_BM_MOVE_MG` | 30 | Slow walking isn't counted as moving: lower it |
| `CONFIG_BM_STILL_MG` | 10 | A helmet on a table isn't counted as still: raise it slightly |
| `CONFIG_BM_OFF_AFTER_S` | 10 | You want faster or more cautious "not on body" alarms |
| `CONFIG_BM_SWING_DPS` | 80 | Normal head turning triggers "carried": raise it. A carried helmet isn't caught: lower it |
| `CONFIG_BM_MATCH_MIN_PCT` | 50 | Same-body detection is too strict or too loose |
| `CONFIG_BM_CADENCE_TOL_X100` | 25 | Rhythm tolerance (0.25 Hz) |
| `CONFIG_BM_BOTH_STILL_S` | 60 | How long both may be still before "unknown" |
| `CONFIG_BM_LOST_AFTER_S` | 10 | Radio dropouts trigger "lost" too easily: raise it |
| `CONFIG_BM_STATUS_EVERY_S` | 30 | Status line rate (0 = only changes) |
| `CONFIG_BM_TOUCH_ON_MS` | 1000 | How long touch "worn" must hold before the helmet counts as ON (vest) |
| `CONFIG_BM_TOUCH_OFF_S` | 3 | How long touch "released" must hold before NOT on body (vest) |
| `CONFIG_BM_KIT_ID` | 5 | Must match on both boards (0–31; helmet `prj.conf` has its own copy) |

**Touch sensor options, in `helmet_motion/prj.conf`:**

| Option | Default | Tune it if… |
|---|---|---|
| `CONFIG_BM_TOUCH_ON_DROP_PCT` | 30 | Wearing doesn't register: lower it to about half the drop you see in the log |
| `CONFIG_BM_TOUCH_OFF_DROP_PCT` | 15 | Removal registers too late: raise it (must stay below ON) |
| `CONFIG_BM_TOUCH_CAL_MS` | 2000 | Baseline measuring time at power-up |
| `CONFIG_BM_TOUCH_DEBOUNCE_MS` | 200 | Brief touches or glitches flip the state |
| `CONFIG_BM_TOUCH_LOG_EVERY_S` | 2 | Touch log rate |
| `CONFIG_BM_HELMET_TOUCH` | y | Set to n when no touch sensor is wired |

**Barometer options, in `vest_motion/prj.conf`:**

| Option | Default | Tune it if… |
|---|---|---|
| `CONFIG_BM_BARO_DEV_CM` | 70 | Bending or crouching triggers it: raise it. A helmet on a low shelf isn't caught: lower it. The status line's `height … cm vs worn` shows the real values |
| `CONFIG_BM_BARO_OFF_S` | 10 | How long the height must stay wrong |
| `CONFIG_BM_BARO` | y | Both boards: set to n to ignore a fitted BMP581 |

The vest's status line shows `baro: learning (walk)` until the worn height is learned, then `height +3 cm vs worn` or similar.

## The PC test

```bash
cd tests
gcc -O2 -I../common test_body_motion.c ../common/motion_features.c ../common/fusion.c ../common/sim_motion.c -lm -o t
./t          # 23 scenarios (8 motion-only, 5 touch, 10 barometer), PASS/FAIL
./t v        # plus every 2 s summary of both boards

# the touch detector: on/off module, analog drop, small drop, drift, worn at power-up, glitch, hysteresis
gcc -O2 -I../common test_touch_level.c ../common/touch_level.c -lm -o tt
./tt         # 7 checks

# the BMP581 driver against a fake register map
gcc -O2 -Ihost_shim -I../common test_bmp581.c ../common/bmp581.c -lm -o tp
./tp         # 8 checks
```

---

## Limits (by design)

- **Both items still:** the touch sensor or the barometers catch a helmet put down while the worker stands still. **With neither**, motion alone cannot tell the two apart and reports "unknown" after 60 s.
- **The barometer learns after each power-up.** Until you have walked about 8 s with both items on, the height check is off. A helmet on a high shelf at head height is not caught by height alone.
- **Bending over for more than 10 s** with the head well below the chest could look like "helmet lower". Raise `CONFIG_BM_BARO_DEV_CM` if your work involves that.
- **The touch signal must drop when worn.** If your module's signal rises instead, the detector never sees "worn". Tell me and I'll add a setting for the other direction.
- **Power up the helmet off.** A baseline taken while worn corrects itself only after the helmet has been taken off once.
- **Head turning vs swinging:** someone shaking their head fast for 10 s could look "carried". Tune `CONFIG_BM_SWING_DPS` with your own data.
- **Not power-optimised:** the helmet broadcasts every 100 ms and the vest listens 50 % of the time. Fine for a test. The reconnect lab shows how to cut that.
- **No security:** the broadcasts are readable by anyone and not authenticated. Fine for a bench test only.

## Files

```text
common/motion_features.c/h   50 Hz IMU data -> 2-second motion summary (portable C)
common/fusion.c/h            the decision rules above (portable C)
common/sim_motion.c/h        simulated walking / standing / table / carried motion
common/touch_level.c/h       helmet touch sensor: power-up baseline, drop = worn (portable C)
common/bmp581.c/h            BMP581 barometer driver (raw I2C, finds 0x47 / 0x46)
common/mpu6050.c/h           accelerometer + gyroscope driver (raw I2C, clones accepted)
common/bm_proto.h            the 24-byte broadcast format
helmet_motion/               helmet firmware (nRF52840 DK)
vest_motion/                 vest firmware (nRF52840 DK; phone link: Nordic UART Service)
tests/test_body_motion.c     the 23-scenario PC test
tests/test_touch_level.c     the 7-check touch detector test
tests/test_bmp581.c          the 8-check BMP581 driver test (with tests/host_shim/)
build.ps1                    build and flash both
```
