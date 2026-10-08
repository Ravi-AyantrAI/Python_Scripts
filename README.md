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
[00:30] Helmet ON body | Vest ON body | H 131mg 1.90Hz 28dps | V 220mg 1.90Hz | match 96%
```

> **Status.** The decision logic passes 8 of 8 scenarios in a PC test that runs exactly the code on the boards. The firmware compiles cleanly against stand-in Zephyr headers but has **not yet been built against your SDK or run on boards**. Expect a first-build fix or two.

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
| 7 | Put both on the table for 70 s | `Both still for 61 s …` | 60–65 s |
| 8 | Walk the helmet out of radio range, or switch its DK off | `Helmet signal LOST` | 10–12 s |

**Simulation instead of a sensor:**

| Board | Button 1 | Button 2 | Button 3 | Button 4 |
|---|---|---|---|---|
| Helmet | Walking | On table | Carried by strap | Standing |
| Vest | Walking | On chair | Standing | Send status now |

For example, set both to walking, then press the helmet's Button 2: about 12–16 s later the phone says *Helmet NOT on body*. LED4 on the helmet means it is simulating.

**LEDs:** on the helmet, LED1 = moving, LED2 = still, LED3 toggles with each broadcast summary, LED4 = simulating. On the vest, LED1 = helmet on body, LED2 = vest on body, LED3 = phone connected, LED4 = message sent.

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
| `CONFIG_BM_KIT_ID` | 5 | Must match on both boards (helmet `prj.conf` has its own copy) |

## The PC test

```bash
cd tests
gcc -O2 -I../common test_body_motion.c ../common/motion_features.c ../common/fusion.c ../common/sim_motion.c -lm -o t
./t          # 8 scenarios, PASS/FAIL
./t v        # plus every 2 s summary of both boards
```

---

## Limits (by design)

- **Both items still means no decision.** A helmet on a table looks the same as a helmet on a worker standing very still. That is what the **proximity sensors** (capacitive, IR) are for; motion matching complements them, it doesn't replace them.
- **Head turning vs swinging:** someone shaking their head fast for 10 s could look "carried". Tune `CONFIG_BM_SWING_DPS` with your own data.
- **Not power-optimised:** the helmet broadcasts every 100 ms and the vest listens 50 % of the time. Fine for a test. The reconnect lab shows how to cut that.
- **No security:** the broadcasts are readable by anyone and not authenticated. Fine for a bench test only.

## Files

```text
common/motion_features.c/h   50 Hz IMU data -> 2-second motion summary (portable C)
common/fusion.c/h            the decision rules above (portable C)
common/sim_motion.c/h        simulated walking / standing / table / carried motion
common/mpu6050.c/h           accelerometer + gyroscope driver (raw I2C, clones accepted)
common/bm_proto.h            the 24-byte broadcast format
helmet_motion/               helmet firmware (nRF52840 DK)
vest_motion/                 vest firmware (nRF52840 DK; phone link: Nordic UART Service)
tests/test_body_motion.c     the 8-scenario PC test
build.ps1                    build and flash both
```
