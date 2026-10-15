# Smart PPE Ecosystem – Test Bench Firmware

> What was optimised in this version, with before/after measurements: see **OPTIMIZATIONS.md**.

A working, scaled-down version of the architecture in the design report:

- a body-area network (helmet ↔ vest over BLE);
- a connectionless BLE uplink from the vest to fixed anchors;
- a **Thread mesh between anchors** that relays traffic to a gateway;
- a hub that de-duplicates, acknowledges, raises alarms and shows a live dashboard.

```
 nRF5340 DK            nRF54L15 DK                 nRF52840 DK #2          nRF52840 DK #1            ESP32
 ┌─────────┐  BLE     ┌───────────┐  BLE ext-adv  ┌──────────────┐ Thread  ┌──────────────────┐ UART ┌──────────┐
 │ HELMET  │◄────────►│   VEST    │──────────────►│ ANCHOR B (2) │════════►│ ANCHOR A (1)     │─────►│   HUB    │
 │ periph. │  GATT    │ BAN hub + │  1M heartbeat │ relay        │  UDP    │ gateway          │◄─────│ web UI   │
 └─────────┘  notify  │ uplink    │  Coded events │              │  mesh   │ (border-router   │      │ rules    │
                      └───────────┘◄──────────────┤ ACK beacon   │◄════════│  stand-in)       │      └──────────┘
                                     ACK beacons  └──────────────┘ mcast   └──────────────────┘
```

| Board | Role | Firmware | Report sections |
|---|---|---|---|
| nRF54L15 DK | **Vest**: BAN central, event engine, fall / man-down logic, uplink | `vest/` | 5.3, 5.4, 6, 7, 9.1 |
| nRF5340 DK | **Helmet**: BLE peripheral, non-contact wear-fusion logic | `helmet/` | 5.2, 7 |
| nRF52840 DK #1 | **Anchor A, ID 1, gateway**: BLE edge + Thread + UART to the hub | `anchor/` + `anchor_a_gateway.conf` | 9.3, 9.4 |
| nRF52840 DK #2 | **Anchor B, ID 2, relay**: BLE edge + Thread, reaches the hub through A | `anchor/` + `anchor_b.conf` | 9.3, 9.4 |
| ESP32 | **Hub**: de-dupe, ACK, siren / evacuation, dashboard | `hub_esp32/` | 10 |

> **Note on the ESP32.** The production design is Nordic-only, with a Linux SBC running OpenThread Border Router as the hub. The ESP32 is fine as a bench hub.
>
> A classic ESP32 has no 802.15.4 radio. So on this bench, **anchor A acts as the border router**: it is the point where mesh traffic leaves the radio network. It hands that traffic to the hub over UART.

---


---

# Step-by-step guide (Windows, nRF Connect SDK v3.x)

Follow these steps in order. Each step ends with a **Check** line, so you know it worked before moving on. Allow about 1–2 hours the first time, mostly installs and first builds.

> **Status of this code.** It was written against the nRF Connect SDK v3.x APIs. The fall-detection logic is unit-tested and every source file passes a syntax and type check, but it has **not yet been compiled against the real SDK**. Expect to fix a few small build errors on the first build. Section 7 (Troubleshooting) lists the likely ones. Send the first error you hit and it can be fixed quickly.

## Step 0 – What you will have at the end

- Four nRF boards running **vest**, **helmet**, **anchor A (gateway)** and **anchor B (relay)**.
- An ESP32 **hub** with a web dashboard.
- A demo where you press a button on the vest and the alarm appears on the dashboard, travelling over BLE and then over the **Thread mesh** between the anchors.

## Step 1 – Install the tools (once)

| Tool | Used for | Where |
|---|---|---|
| **nRF Connect for VS Code** extension + **nRF Connect SDK v3.4.1** and **toolchain v3.4.0** | Building and flashing the four nRF boards | VS Code → Extensions → "nRF Connect for VS Code Extension Pack" → *Manage SDKs* / *Manage toolchains* |
| **nRF Util** (`nrfutil`) with the `device` command | Listing boards, flashing | Installed with the extension. Check below. |
| **Arduino IDE 2.x** + **esp32 by Espressif** board package | Flashing the ESP32 hub | Arduino IDE → Boards Manager |
| A serial terminal (**nRF Terminal** in VS Code, PuTTY, or Tera Term) | Reading the boards' logs | nRF Terminal is part of the extension |

Open the terminal from the nRF Connect extension, then run:

```powershell
west --version
nrfutil device list
```

**Check:** `west --version` prints a version, and `nrfutil device list` runs (it may list nothing if no board is plugged in yet).

## Step 2 – Put the files in place

1. Unzip `Smart_PPE_Testbed_Firmware.zip`.
2. Copy the contents to a **short path** with no spaces, for example `D:\ppe_thread`. Long paths cause build errors on Windows, especially for the nRF5340.
3. You should see these folders and files:

```
D:\ppe_thread\
  anchor\   common\   helmet\   hub_esp32\   tests\   vest\
  build_all.ps1   build_all.sh   README.md
```

**Check:** `D:\ppe_thread\vest\CMakeLists.txt` exists.

## Step 3 – Label your boards and find their serial numbers

Plug in all four nRF boards by USB, then run:

```powershell
nrfutil device list
```

Each board has a serial number (about 9–10 digits). Match them to the boards by the board name printed in the list, then stick a label on each board.

| Label | Board | Role |
|---|---|---|
| **VEST** | nRF54L15 DK | Vest |
| **HELMET** | nRF5340 DK | Helmet |
| **ANCHOR-A** | nRF52840 DK #1 | Gateway anchor (will be wired to the ESP32) |
| **ANCHOR-B** | nRF52840 DK #2 | Relay anchor |

The two nRF52840 DKs look identical. Plug in **one at a time** to see which serial is new, and label it straight away. Note the serial numbers somewhere, since you will need them in the next steps.

**Check:** you have four labelled boards and four serial numbers written down.

## Step 4 – Build the firmware

In the nRF Connect terminal:

```powershell
cd D:\ppe_thread
powershell -ExecutionPolicy Bypass -File .\build_all.ps1
```

This builds all four images into `D:\ppe_thread\build\vest`, `helmet`, `anchor_a` and `anchor_b`. A summary table at the end shows `OK` or `FAILED` for each.

Tip: build one board at a time the first time, so a failure is easy to understand:

```powershell
.\build_all.ps1 -Only vest
.\build_all.ps1 -Only helmet
.\build_all.ps1 -Only anchor_a
.\build_all.ps1 -Only anchor_b
```

**Check:** the summary shows `OK` for all four. For both anchors you should also see a green line: `Verified: anchor ID 1, role GATEWAY` (anchor_a) and `Verified: anchor ID 2, role RELAY` (anchor_b). If one shows `FAILED`, copy the **first** `error:` line and the file name it mentions (see Section 7).

> **Why the anchors use `--no-sysbuild`.** With sysbuild (the default in NCS 3.x) a plain `-DEXTRA_CONF_FILE=…` is not passed to the application. Both anchors then silently build as *relay, ID 1* and no gateway exists. The script builds the anchors without sysbuild and verifies the role and ID of each build. If you build by hand, use the commands in Section 3.

## Step 5 – Flash the four nRF boards

Replace the serial numbers with your own:

```powershell
.\build_all.ps1 -Flash -SnVest 1050AAAAAA -SnHelmet 1050BBBBBB -SnAnchorA 6836CCCCCC -SnAnchorB 6836DDDDDD
```

This rebuilds, then flashes each board with a full erase. The erase matters: it clears any old Thread network settings stored on the board. To flash without rebuilding, use the `west flash` commands in Section 3.

**Check:** the summary table shows `OK` in both the Build and Flash columns for all four. LEDs may start blinking.

## Step 6 – Flash the ESP32 hub

1. Open `D:\ppe_thread\hub_esp32\hub_esp32.ino` in Arduino IDE. The folder must contain **three files**: `hub_esp32.ino`, `ppe_proto.h` and `hub_types.h`. The IDE shows them as tabs. The folder name must stay `hub_esp32`, the same as the `.ino` file.
2. Choose your board: *Tools → Board → esp32 →* **ESP32 Dev Module** (or the one that matches your board).
3. Choose the port: *Tools → Port →* the new COM port that appears when you plug in the ESP32.
4. Optional: to join your own Wi-Fi, fill in `WIFI_SSID` and `WIFI_PASS` at the top of the sketch. If you leave them empty, the ESP32 creates its own Wi-Fi network called **PPE-HUB** (password **ppe12345**).
5. Click **Upload**.
6. Open *Tools → Serial Monitor* at **115200 baud**.

**Check:** the serial monitor shows a line like `Access point 'PPE-HUB' - dashboard at http://192.168.4.1`.

A message such as *"Multiple libraries were found for WiFi.h … Used: …esp32\libraries\WiFi"* is only informational. The IDE picked the ESP32's built-in WiFi library, which is the correct one.

## Step 7 – Wire the ESP32 to anchor A

Unplug USB from both boards first. Use three jumper wires and a 1 kΩ resistor:

| ANCHOR-A (nRF52840 DK #1) | | ESP32 |
|---|---|---|
| **P1.02** (TX) | → | **GPIO16** (RX) |
| **P1.01** (RX) | ← **1 kΩ** ← | **GPIO17** (TX) |
| **GND** | ↔ | **GND** |

- Put the resistor in series with the wire from ESP32 GPIO17 to P1.01.
- Only anchor A is wired to the hub. Anchor B just needs USB power.
- If your ESP32 board is a C3, C6 or S3 type, GPIO16/17 may not exist. Change `NRF_RX_PIN` and `NRF_TX_PIN` at the top of the sketch to pins your board has.

**Check:** wires are firmly seated, TX goes to RX and RX goes to TX (crossed), and GND is connected.

## Step 8 – Open the log windows

Each nRF board shows up as a serial (COM) port with **115200 baud**. `nrfutil device list` shows which COM port belongs to which serial number. Open a terminal window per board and name them (VEST, HELMET, ANCHOR-A, ANCHOR-B).

- On the **nRF5340** and **nRF54L15** boards you may see two COM ports per board. If one is silent, use the other.
- The anchors also give you an **interactive shell**: type `ppe status` and press Enter.

**Check:** you can see log text from each board. If a window is empty, press the board's **RESET** button.

## Step 9 – Power up in this order and check each stage

Power-cycle everything, then bring the system up one stage at a time.

### 9a. Hub and gateway link
1. Power the **ESP32** (USB).
2. Power **ANCHOR-A** (USB). Wait about 10 seconds.
3. Connect your PC or phone to the Wi-Fi **PPE-HUB** and open **http://192.168.4.1**.

**Check:**
- The ANCHOR-A boot log says `PPE anchor 1 starting as GATEWAY` and, a moment later, `hub UART ready`.
- The dashboard says **Gateway link: OK**. Anchor A's LED1 is steady.

**If the dashboard says `NO RESPONSE` and LED1 blinks slowly (about once per second):** that blink is the "no link yet" signal. Read the first boot lines of ANCHOR-A:

| What the log says | Meaning | Fix |
|---|---|---|
| `PPE anchor 1 starting as RELAY` (or `anchor 2 …`) on a board meant to be A | This board was built without the gateway role | Rebuild with `.\build_all.ps1 -Only anchor_a` (it verifies the role), then reflash with `--erase` |
| Both anchors say `anchor 1 … RELAY` | Both were built without their role files. There is no gateway, and the duplicate ID also makes the anchors ignore each other | Rebuild and reflash **both** anchors |
| `PPE anchor 1 starting as GATEWAY` but no `hub UART ready` line | UART problem on the nRF side | Check the `uart1` overlay was built (`anchor/boards/nrf52840dk_nrf52840.overlay`) |
| `hub UART ready` is shown, but still `NO RESPONSE` | Wiring | Swap the two data wires (TX must go to RX), check GND is shared, and check the 1 kΩ resistor is in the ESP32 GPIO17 → P1.01 wire |

Garbage lines such as `? ����` on the ESP32 serial monitor are line noise (a floating or glitching RX wire, often when the nRF resets). The hub now ignores them.

### 9b. Thread mesh between the two anchors
1. Power **ANCHOR-B**. Wait 15–30 seconds.
2. In each anchor's log window, type `ot state` and press Enter.

**Check:**
- One anchor says `leader` and the other says `router` (or `child`, which is fine).
- ANCHOR-B's log shows `gateway anchor 1 found at fd…`. Its LED1 turns steady.
- Within about 15 seconds both anchors appear in the dashboard's **Anchors** table.

If the anchors do not join each other, see Section 7.

### 9c. Helmet and vest
1. Power the **HELMET**. The log says `Advertising as kit 1`.
2. Power the **VEST**.

**Check:**
- The vest log shows `helmet connected - discovering service` and then `BAN up: subscribed to helmet status`.
- The vest's LED0 is steady, and the helmet's LED1 is on.
- After about 10 seconds the dashboard's **Workers** table lists the vest, with `helmet = NOT WORN`.

The whole chain is now running. Next, three short demos.

## Step 10 – Demo 1: "worn" detection

The helmet has no proximity sensor, so BTN1 stands in for "put on / take off". With a real MPU-6050, the vest's on-body detection gives the real verdict; see *On-body detection*.

1. Press **HELMET BTN1**. After about 3 seconds LED2 stays on and the dashboard shows `helmet: worn`.
2. Press **HELMET BTN4** (hand inside a helmet resting on a table). LED2 **blinks**, which means `uncertain`. The system correctly refuses to call it "worn".
3. Press **HELMET BTN1** once: the helmet goes back to worn. Press it again to take the helmet off. After about 15 seconds the vest sends a `HELMET_OFF` alert and the dashboard row turns red.

## Step 11 – Demo 2: SOS across the mesh (the main test)

1. **Direct path:** hold **VEST BUTTON 0** for **2 seconds**.
   - The vest's LED1 comes on, then LED2 flashes when an anchor receives it, then LED2 stays on for 2 seconds when the **hub** confirms.
   - The dashboard log shows `SOS P0 … via anchor …` and `siren ON`. The closest anchor's LED4 blinks fast.
2. Silence the siren: press **BTN4 on that anchor** (or use the dashboard's *Silence sirens* button).
3. **Multi-hop path (this is the Thread test):** press **BTN1 on ANCHOR-A**. Its log says `BLE edge OFF`, so it no longer hears the vest, and only anchor B can.
4. Hold **VEST BUTTON 0** for 2 seconds again.

**Check:** the dashboard log says **`via anchor 2 RELAYED OVER THREAD`**, and ANCHOR-A's log shows `relayed via mesh from anchor 2`. The vest still gets its hub confirmation. This proves the message went vest → anchor B → Thread → anchor A → hub, and the confirmation came back through the mesh.

5. Press **BTN1 on ANCHOR-A** again to turn its radio edge back on.

## Step 12 – Demo 3: falls and man-down

1. **Fall:** short-press **VEST BUTTON 1**. The vest logs `FALL candidate…` and starts a 10-second pre-alert (LED1 fast blink). When it ends, a `FALL` alarm reaches the hub.
2. **Cancel:** repeat, and short-press **VEST BUTTON 0** during the pre-alert. A `CANCELLED` note is logged and no siren sounds. This is the false-alarm control from the report.
3. **Fall from height:** hold **VEST BUTTON 1** for 1.5 seconds and release. The log shows a drop of about 250 cm and the alarm is `FALL_FROM_HEIGHT`.
4. **Man-down:** after a fall, the simulated worker stays lying down. After 20 seconds a prompt appears ("ARE YOU OK?"). Do nothing for 10 more seconds and a `MAN_DOWN` alarm is sent. Short-press **VEST BUTTON 0** during the prompt to answer instead.

## Step 13 – More tests

The full 17-test plan is in Section 5. A few worth trying next:

| Test | What to do | What it shows |
|---|---|---|
| Hub failure | Unplug the ESP32 TX wire, then press SOS | No hub confirmation: after 10 s the anchors raise their own siren (local autonomy) |
| Gateway failure | Power off ANCHOR-A | After 35 s anchor B reports it lost the gateway; power A back on and B re-learns it |
| Evacuation | Press *Evacuate site* on the dashboard | The order reaches the vest through the mesh: vest LED3 blinks fast |
| Helmet link loss | Unplug the helmet | The vest raises `HELMET_LINK_LOST`, **not** "helmet removed" |
| Range | On an anchor, type `ppe rssi -55` | The anchor ignores weak vest packets, simulating a smaller range |

## Step 14 – Useful commands while testing

Type these into an **anchor's** log window:

| Command | What it does |
|---|---|
| `ppe status` | Anchor ID, role, packet counts, gateway/hub link, pending events |
| `ppe edge off` / `ppe edge on` | Same as BTN1: stop/start hearing vests |
| `ppe rssi -60` | Ignore vest packets weaker than −60 dBm |
| `ppe siren on` / `ppe siren off` | Test the local siren |
| `ot state` | `leader`, `router` or `child` |
| `ot neighbor table` | Which anchors can hear each other, with signal strength |
| `ot router table` | Routes: the next hop towards each other anchor |
| `ot txpower -20` | Lower the Thread transmit power (shrinks the mesh range) |
| `ot dataset active` | Shows the network name, channel and key (should match on both anchors) |

## Step 15 – Re-running, resetting and changing things

- **Restart everything:** unplug all boards and the ESP32, then repeat Step 9 in order.
- **Start from a clean state:** run the flash command from Step 5 again. It erases the boards first.
- **Change a setting, then rebuild one board:** for example, to change the kit ID, edit `CONFIG_PPE_KIT_ID` in `vest\Kconfig` and `helmet\Kconfig` (the default is 1 on both, so they match). Then run `.\build_all.ps1 -Only vest -Flash -SnVest 1050AAAAAA`.
- **A second Thread hop:** needs a third board. See the end of Section 5.

---


---

# Adding real sensors (MPU-6050 and BMP581)

This build uses exactly two kinds of sensor, one of each on the helmet and on the vest:

| Sensor | Used for |
|---|---|
| **MPU-6050** (GY-521 board) | Helmet: head impacts, motion, orientation. Vest: posture, falls, man-down, motion. Both: on-body detection |
| **BMP581** (e.g. 7Semi board) | Helmet height above the vest (on-body detection). On the vest also the barometric fall height |

Both are detected at boot. A board without an MPU-6050 simulates its motion with the buttons. Without a BMP581, the height checks simply stay off.

## S1 – Check the I/O voltage BEFORE wiring

| Board | I/O voltage | What to do |
|---|---|---|
| Helmet: nRF5340 DK | 3.0 V | Nothing |
| Vest: nRF54L15 DK | **1.8 V by default** | Set VDD to **3.3 V** in *nRF Connect for Desktop → Board Configurator*. The GY-521 and BMP581 boards pull their lines up to about 3.3 V |

Power every module from the DK's **VDD** pin and GND, never from 5 V.

## S2 – Wire the helmet (nRF5340 DK)

Both sensors share one I2C bus:

| Sensor pin | Helmet DK |
|---|---|
| SDA | **P1.02** (Arduino SDA) |
| SCL | **P1.03** (Arduino SCL) |
| VCC / GND | VDD / GND |

The MPU-6050 sits at 0x68 and the BMP581 at 0x47 (0x46 if its SDO is tied to GND). Mount the board firmly on the helmet. On-body detection learns its orientation while worn, so any fixed angle works.

## S3 – Wire the vest (nRF54L15 DK)

| Sensor pin | Vest DK |
|---|---|
| SDA | **P1.12** |
| SCL | **P1.11** |
| VCC / GND | VDD (3.3 V, see S1) / GND |

Mount the MPU-6050 firmly, ideally upright on the chest or belly. A sensor hanging on its wires swings and confuses the motion checks.

## S4 – Rebuild and flash helmet and vest

Rebuild both after wiring. Nothing needs to change in the configuration: both sensors are found automatically.

## S5 – Check what was detected (boot log)

Each board lists every device on its sensor bus, then reports each sensor. The helmet shows, for example:

```text
sensor I2C bus: devices found: 0x47 0x68 (MPU-6050 0x68, BMP581 0x47/0x46)
BMP581 ok at 0x47, 100512 Pa (chip ID 0x50): helmet height sent to the vest
MPU-6050 (WHO_AM_I 0x68) at 0x68: REAL impacts and helmet motion
```

If a sensor is missing, the log says exactly why. For example `no device answers at 0x47 or 0x46` means the wiring, power, or (for the BMP581) a CSB pin not tied high.

## S6 – Calibrate

After every reset, **put both on and walk normally for about 10 s.** The vest learns how the helmet and the vest are oriented, and how high the helmet sits above the vest, when worn. See *On-body detection* below.

## S7 – Tests with real sensors

| # | Test | Do this | Expected |
|---|---|---|---|
| R1 | Walking, both worn | Walk 30 s | Vest log: `on-body: helmet ON, vest ON` |
| R2 | Helmet put down | Put the helmet on a table and keep walking | `HELMET_NOT_ON_BODY` within about 15 s |
| R3 | Helmet carried | Carry the helmet by hand at vest height, or upside down by its strap | `HELMET_CARRIED` within about 10–15 s |
| R4 | Head impact | Tap the helmet sensor sharply (above 6 g) | `HEAD_IMPACT` event at the hub |
| R5 | Fall | Drop the vest onto a cushion from about 1 m | Fall pre-alert, then `FALL` (barometric height if the vest has a BMP581) |

## S8 – Troubleshooting real sensors

| Symptom | Cause / fix |
|---|---|
| `devices found: none` | SDA/SCL swapped or on the wrong pins, or no common GND |
| MPU-6050 found, motion looks wrong | Mount it firmly; a dangling sensor swings |
| `BMP581 not used: …` | Read the reason. Most often power, or the board's CSB pin not tied high (I2C mode) |
| On-body never calibrates | Walk with **both** worn; the MPU-6050 must be real on both boards |

## S9 – What is still simulated

- **Helmet head proximity:** this build has no proximity sensor. The helmet's own WORN / UNCERTAIN / NOT WORN state uses the button simulation (BTN1) plus real motion from the MPU-6050. The real on-body verdict comes from the vest's MPU + BMP algorithm.
- **Vest presence:** reported as worn. Whether the vest is really on the body comes from the on-body algorithm (`VEST_NOT_ON_BODY`).
- **Heart rate, SpO₂, IR proximity:** not measured; sent as 0 ("not available").

---

# On-body detection: motion, orientation and height (MPU-6050 + BMP581)

The vest decides whether the helmet and the vest are each on the worker's body by comparing them. This is the same algorithm as the body-motion lab (`common/sensors/motion_features.c` and `fusion.c`, unchanged), fed over the BAN link:

| Check | Sensor | What it catches |
|---|---|---|
| Moving together (step rhythm) | MPU-6050 on both | Helmet left on a table while the worker walks; vest left on a chair |
| Rotation | Helmet gyro | Helmet swinging from its strap (> 100 °/s) |
| **Orientation** | MPU-6050 on both | Helmet tilted ≥ 75° from its worn orientation while the vest stays upright, e.g. upside down on its strap |
| **Height** | BMP581 on both | Helmet ≥ 40 cm lower than when worn (carried at hand or vest height, put down while the worker stands still); vest far below a worn helmet |
| Posture | Vest orientation | Vest tilted ≥ 45° (lying down, bending): height and tilt are explained by the body, so those checks are skipped |

## Calibrate after every reset

Put both on and walk normally for about 10 s. The vest log shows:
- `Orientation calibrated while worn (learned)`
- `Barometers calibrated while worn (…) (learned)`

These worn references are then **frozen**, following only small drift, so a carried helmet can't pull them along. Returning to "ON" after "NOT on body" or "carried" needs about 4 s of consistent evidence, so the verdict doesn't flip back during a calm moment.

## Events at the hub

Unchanged: `HELMET_NOT_ON_BODY` (P1), `HELMET_CARRIED` (P2), `VEST_NOT_ON_BODY` (P1). The reason appears in the vest log, for example `Helmet moving, NOT worn? (tilted 176 deg from worn while the vest is upright: carried?)`.

## Wiring the BMP581 (one per board, on the existing sensor bus)

| Board | SDA | SCL | Shares the bus with |
|---|---|---|---|
| Helmet (nRF5340 DK) | P1.02 | P1.03 | MPU-6050 (0x68) |
| Vest (nRF54L15 DK) | P1.12 | P1.11 | MPU-6050 (0x68) |

- **Address:** the BMP581 answers at 0x47 (or 0x46), so there are no clashes.
- **Power:** VCC to the DK's VDD, GND to GND. On the nRF54L15 DK, set VDD to 3.3 V in Board Configurator, as for the MPU-6050.
- **Boot log:** each board lists every device found on its sensor bus, then says whether the BMP581 is used, or exactly why not.

**Bonus:** the vest's BMP581 also feeds the fall detector's pressure input, so a fall from height is measured by pressure change (Δh ≥ 60 cm) instead of being estimated from free-fall time.

## How it is carried over the BAN link

- **Motion summary:** the helmet's 20-byte motion summary is unchanged.
- **New "pose" characteristic:** a 5-byte notification sent just before each summary. It carries the gravity direction, and the pressure as the low 16 bits of Pa×8; the vest restores the full value from its own reading. A separate characteristic avoids changing the ATT MTU.
- **Older helmet firmware:** the vest logs that the helmet has no pose characteristic and runs motion-only.
- **Time alignment:** summaries arrive 0–1 s late over the 1 s link. The vest aligns its own pressure using the motion-shape lag when the shapes correlate, and assumes 0.48 s otherwise. It skips the height check while the whole worker rises or falls faster than 0.4 m/s (a lift).

## Tuning

Every 10 s the vest logs what the algorithm sees, for example:

```text
on-body: helmet ON, vest ON | H 96 mg 1.30 Hz 44 dps | V 30 mg 1.15 Hz | height -3 cm vs worn | tilt H 6 V 4 deg
```

Settings, in `vest/prj.conf`:

| Option | Default | Meaning |
|---|---|---|
| `CONFIG_PPE_BM_TILT_DEG` | 75 | Helmet tilt that counts as "not worn" |
| `CONFIG_PPE_BM_UPRIGHT_DEG` | 35 | Vest must stay within this |
| `CONFIG_PPE_BM_LYING_DEG` | 45 | Vest tilt meaning lying or bending |
| `CONFIG_PPE_BM_TILT_OFF_MS` | 4000 | How long the tilt must hold |
| `CONFIG_PPE_BM_BARO_DEV_CM` | 40 | Height change vs worn that counts |
| `CONFIG_PPE_BM_BARO_OFF_S` | 8 | How long the height must stay wrong |
| `CONFIG_PPE_BM_SWING_DPS` | 100 | Rotation meaning "swinging" |
| `CONFIG_PPE_BM_ON_CONFIRM_MS` | 3800 | Evidence needed to return to ON |
| `CONFIG_PPE_BM_MOVE_CONFIRM_MS` | 5000 | The other item must keep moving this long (rejects desk knocks) |
| `CONFIG_PPE_BM_LOG_EVERY_S` | 10 | Status log interval; 0 = off |
| `CONFIG_PPE_BARO` | y | Set to n on a board to ignore its BMP581 (also in `helmet/prj.conf`) |

The helmet's own wear state (button-simulated proximity plus real motion, see S9) runs alongside this and still drives `HELMET_OFF`.

## PC tests

```bash
cd tests
gcc -O2 -I../common/sensors -I. test_body_motion.c ../common/sensors/motion_features.c ../common/sensors/fusion.c sim_motion.c -lm -o t && ./t          # 25 scenarios
gcc -O2 -I../common/sensors -I. test_body_motion_ppe.c ../common/sensors/motion_features.c ../common/sensors/fusion.c sim_motion.c -lm -o tpd && ./tpd  # same, PPE BAN delivery
gcc -O2 -Ihost_shim -I../common/sensors test_bmp581.c ../common/sensors/bmp581.c -lm -o tp && ./tp   # BMP581 driver, 9 checks
```

---

# Recording and profiling with SEGGER SystemView

SystemView records what the firmware does **while it runs**: every thread switch, every interrupt and kernel call, and the PPE markers. It shows them live on a timeline, with CPU load per thread and the duration of each marked job. It uses the DK's on-board J-Link (over RTT), so no extra hardware is needed.

## T1 — Install

Install **SEGGER SystemView** for Windows from segger.com. It uses the J-Link drivers that come with nRF Connect. Check SEGGER's licence terms for your kind of use.

## T2 — Make a trace build

In the `prj.conf` of the board you want to look at (`vest`, `helmet` or `anchor`), uncomment the **TRACE build** block at the end:

```text
CONFIG_TRACING=y
CONFIG_SEGGER_SYSTEMVIEW=y
CONFIG_USE_SEGGER_RTT=y
CONFIG_THREAD_NAME=y
CONFIG_THREAD_RUNTIME_STATS=y
CONFIG_THREAD_ANALYZER=y
CONFIG_THREAD_ANALYZER_AUTO=y
CONFIG_THREAD_ANALYZER_AUTO_INTERVAL=30
```

Rebuild and flash only that board. For example: `.\build_all.ps1 -Flash -Only vest -SnVest <serial>`.

The normal log still comes out on the UART, and every 30 s it now also prints each thread's CPU share and peak stack use.

## T3 — Record

1. Keep the DK connected by USB. Close any other program using its J-Link, such as a debug session.
2. In SystemView: *Target → Recorder Configuration* → **J-Link**, interface **SWD**, speed 4000 kHz. Set the target device to match the board:

| Board | Device |
|---|---|
| Vest | nRF54L15_M33 |
| Helmet | nRF5340_xxAA_APP |
| Anchor | nRF52840_xxAA |

3. RTT control block: leave it on **Auto Detection**. If SystemView can't find it, look up the address of `_SEGGER_RTT` in the build folder's `zephyr/zephyr.map` and enter it.
4. Press **Start Recording**. After about 10 s the PPE marker names appear (the firmware re-sends them every 10 s).

## T4 — What to look at

| Marker | Board | Shows |
|---|---|---|
| IMU sample | Vest | One 50 Hz sample: read, posture, fall detector. Should repeat every 20 ms and be short |
| On-body decision | Vest | One motion-matching decision, every 1.92 s. Its duration is the algorithm's CPU cost |
| Uplink send | Vest | Building and handing one BLE uplink burst to the radio |
| Helmet notify | Vest | Handling one helmet notification (status or motion) |
| Sensor poll | Helmet | The 20 ms IMU + barometer poll |
| Wear fusion | Helmet | The 250 ms wear decision (single mark) |
| Motion to vest | Helmet | Sending the motion summary |
| Vest packet | Anchor | Processing one received vest packet |
| Mesh/UART TX | Anchor | Forwarding towards the hub |
| Mesh RX | Anchor | Handling one Thread message |
| Retry pass | Anchor | The 500 ms retry / local-autonomy check (single mark) |

On-body verdict changes also appear as **messages** in SystemView's terminal view, at the moment they happen on the timeline.

**Useful checks:**
- **CPU load:** the context view shows each thread's share. The vest's `motion` thread should stay small even with the on-body decision.
- **Timing jitter:** gaps between *IMU sample* markers larger than 20 ms mean something is blocking the motion thread.
- **Who blocks whom:** after an SOS button press, follow the work queue → *Uplink send* → Bluetooth threads on the timeline.
- **Overflows:** if SystemView reports them, stop recording other boards on the same PC, or add `CONFIG_SEGGER_SYSVIEW_RTT_BUFFER_SIZE=8192` from the TRACE block.

## T5 — Back to a normal build

Comment the TRACE block out again before power measurements. Tracing keeps the CPU and the debugger busy and changes both timing and current.


# Reference

## 1. What you need

- nRF Connect SDK **v3.x** (written for the v3.0 API; the target setup is **v3.4.1** with toolchain v3.4.0), via nRF Connect for VS Code or `west`.
- Arduino IDE 2.x with the **esp32 board package** (2.x or 3.x).
- 3 jumper wires and a **1 kΩ resistor**.

## 2. Wiring: anchor A (nRF52840 DK #1) ↔ ESP32

| nRF52840 DK #1 | | ESP32 DevKit |
|---|---|---|
| P1.02 (UART TX) | → | GPIO16 (RX) |
| P1.01 (UART RX) | ← 1 kΩ ← | GPIO17 (TX) |
| GND | ↔ | GND |

- **Why the resistor:** the DK runs at 3.0 V and the ESP32 drives 3.3 V, so the resistor limits the current into the nRF pin.
- **Other ESP32 boards:** on ESP32-C3, C6 or S3 boards, change `NRF_RX_PIN` / `NRF_TX_PIN` in the sketch.
- **Anchor B** needs only USB power.

## 3. Build and flash

**Windows (PowerShell, recommended):** use `build_all.ps1`. See Steps 4 and 5 of the step-by-step guide above.

```powershell
.\build_all.ps1                       # build all
.\build_all.ps1 -Only anchor_a        # build one (vest, helmet, anchor_a, anchor_b)
.\build_all.ps1 -Flash -SnVest <sn> -SnHelmet <sn> -SnAnchorA <sn> -SnAnchorB <sn>
```

**Linux / macOS (bash):**

```bash
# all at once (edit the J-Link serials inside first: `nrfutil device list`)
./build_all.sh flash

# or one by one
west build -b nrf54l15dk/nrf54l15/cpuapp vest   -d build/vest
west build -b nrf5340dk/nrf5340/cpuapp   helmet -d build/helmet     # sysbuild also builds the net core
west build --no-sysbuild -b nrf52840dk/nrf52840 anchor -d build/anchor_a -- -DEXTRA_CONF_FILE=anchor_a_gateway.conf
west build --no-sysbuild -b nrf52840dk/nrf52840 anchor -d build/anchor_b -- -DEXTRA_CONF_FILE=anchor_b.conf
west flash -d build/<name> --erase --dev-id <serial>
```

**Hub:**
1. Open `hub_esp32/hub_esp32.ino`.
2. Optionally set `WIFI_SSID` / `WIFI_PASS` (leave them empty to create the access point `PPE-HUB`, password `ppe12345`).
3. Flash the sketch.
4. Open the dashboard at the address printed on the USB serial monitor. In access-point mode that is **http://192.168.4.1**.

**Serial consoles:** every DK appears as a J-Link virtual COM port at 115200 baud. Use the nRF Terminal in VS Code, PuTTY or `screen`. The anchors have an interactive shell.

## 4. Controls

**Vest – nRF54L15 DK** (`DK_BTN1` = the button labelled **BUTTON 0** on the board, and so on)

| Button | Short press | Hold |
|---|---|---|
| BUTTON 0 | Cancel fall pre-alert / answer "Are you OK?" | **2 s → SOS** |
| BUTTON 1 | Simulated fall, 0.8 m | **1.5 s → fall from height, 2.5 m** |
| BUTTON 2 | Toggle vest closed/open | |
| BUTTON 3 | Toggle lying posture (simulation only) | **2 s → re-calibrate 'upright'** (real MPU-6050) |

| Vest LED | Meaning |
|---|---|
| LED 0 | Helmet BAN link: on = linked, slow blink = searching |
| LED 1 | Fast blink = pre-alert / prompt; on = P0 waiting for the hub ACK |
| LED 2 | Short flash = an anchor received the event; 2 s on = **the hub ACKed** |
| LED 3 | Heartbeat flash; fast blink = buddy alert or **evacuation** |

**Helmet – nRF5340 DK**
- **BTN1:** helmet on/off head.
- **BTN2:** head impact.
- **BTN3:** chin strap.
- **BTN4:** spoof test (a hand inside the helmet on a table).
- **LED1:** linked. **LED2:** worn (blinks = uncertain). **LED3:** impact. **LED4:** BMP581 barometer working.

**Anchors – nRF52840 DK**
- **BTN1:** toggle the BLE edge, which simulates "this anchor is out of the vest's range".
- **BTN4:** silence the local siren.
- **LED1:** link (gateway: hub alive; relay: gateway known). **Steady = linked. A slow blink (about 1 Hz) = no link yet.**
- **LED2:** vest packet.
- **LED3:** event pending.
- **LED4:** siren (fast) / evacuation (slow).

Shell commands on the anchors: `ppe status`, `ppe edge on|off`, `ppe rssi -60`, `ppe siren on|off`, plus all OpenThread commands under `ot`.

## 5. Test plan

Run the tests in order. Each "Expected" column describes what you should see.

| # | Test | Steps | Expected |
|---|---|---|---|
| 1 | **Thread mesh forms** | Power both anchors and wait about 15 s. Run `ot state` on each. | One shows `leader`, the other `router` (or `child`). Anchor B logs `gateway anchor 1 found at fdxx:…`. Its LED1 is steady. |
| 2 | **Hub link** | Power the ESP32. | Anchor A LED1 is steady. Dashboard shows "Gateway link: OK" and both anchors after their health reports (≤ 15 s). |
| 3 | **BAN** | Power the helmet and vest. | Vest LED0 is steady. Vest logs `BAN up: subscribed to helmet status`. |
| 4 | **Wear fusion** | Helmet BTN1 (on head). | After 3 s the helmet shows WORN (LED2 on). The dashboard helmet column shows `worn`. |
| 5 | **Spoof rejected** | Helmet BTN4. | The helmet goes to UNCERTAIN (LED2 blinks), never WORN, so no false "worn". |
| 6 | **Helmet removed** | BTN1 again (off head). Wait. | NOT_WORN after 5 s. The vest raises `HELMET_OFF` (P1) about 10 s later. The hub log shows it and ACKs it. |
| 7 | **Link loss ≠ removal** | Unplug the helmet. | The vest logs "link lost – NOT treated as helmet removed". After 30 s the heartbeat alerts show `HELMET_LINK_LOST`. No `HELMET_OFF` event. |
| 8 | **SOS end-to-end** | Hold vest BUTTON 0 for 2 s. | Vest LED1 on. The anchor ACK flashes LED2. The hub logs `SOS P0 …`, sends the ACK and **siren ON** at the closest anchor (its LED4 fast-blinks). The vest logs `HUB ACK … after N ms` and LED2 stays on for 2 s. |
| 9 | **Fall detection** | Short press BUTTON 1. | `FALL candidate … dh 80 cm` → 10 s pre-alert (LED1 fast) → `FALL` P0 → ACK as in test 8. |
| 10 | **False alarm cancelled** | Repeat 9 and short-press BUTTON 0 during the pre-alert. | `CANCELLED` (P2) is sent and logged. No siren. |
| 11 | **Fall from height** | Hold BUTTON 1 for 1.5 s. | `FALL_FROM_HEIGHT`, dh ≈ 250 cm. |
| 12 | **Man-down** | After test 9 (the worker stays lying), or press BUTTON 3. Wait. | After 20 s still: "ARE YOU OK?" prompt. No answer within 10 s → `MAN_DOWN` P0. |
| 13 | **Multi-hop relay** ★ | Press **BTN1 on anchor A**, so A no longer hears vests. Trigger SOS. | Only anchor B hears the vest. The hub shows **"via anchor 2 RELAYED OVER THREAD"**. Anchor A logs `relayed via mesh from anchor 2`. The ACK returns by multicast through the mesh to B's ACK beacon. |
| 14 | **Local autonomy** | Disconnect the ESP32 (or its TX wire). Trigger SOS. | No hub ACK. After 10 s the anchors log `LOCAL SIREN (autonomy)` and LED4 blinks. Reconnect: the retried event is ACKed and pending clears. |
| 15 | **Gateway loss** | Power off anchor A. | After 35 s anchor B logs "gateway announcements lost" and falls back to multicast. Power A back on: B re-learns the gateway, and pending events drain. |
| 16 | **Evacuation broadcast** | Press "Evacuate site" on the dashboard. | Hub → A → multicast → B. Both ACK beacons carry the flag. The vest logs `EVACUATION ORDERED` and LED3 fast-blinks. "All clear" clears it. |
| 17 | **Zone** | Move the vest closer to each anchor. | The dashboard "Zone" column follows the strongest anchor. |

**Range tests on a desk.**
- `ppe rssi -55` on an anchor makes it ignore weaker vest packets.
- `ot txpower -20` shrinks the Thread link range.

**Seeing more than one Thread hop.** With two anchors the mesh path B → A is one hop. To see two or more hops, add a third Thread FTD (any nRF52840 dongle or DK with this anchor firmware and `CONFIG_ANCHOR_ID=3`). Then block the direct A↔C link:

```
ot extaddr                          # on C: note its extended address
ot macfilter addr add <C-extaddr>   # on A
ot macfilter addr denylist          # on A
```

Repeat the reverse on C. Traffic from C now flows C → B → A. Check it with `ot router table` (look at the next-hop column).

## 6. Host unit test (no hardware)

```bash
cd tests
gcc -O2 -I../vest/src test_fall_detect.c ../vest/src/fall_detect.c -lm -o t && ./t
```

This runs 4 falls and 4 common false-alarm activities through the exact detector used on the vest.

```bash
gcc -O2 -I../common/sensors -I. test_body_motion.c ../common/sensors/motion_features.c ../common/sensors/fusion.c sim_motion.c -lm -o tb && ./tb
gcc -O2 -Ihost_shim -I../common/sensors test_bmp581.c ../common/sensors/bmp581.c -lm -o tp && ./tp
```

These run the on-body algorithm (25 scenarios) and the BMP581 driver (9 checks). See *On-body detection* for the PPE-delivery variant.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Both anchors boot as `anchor 1 … RELAY`, hub shows `NO RESPONSE`, LED1 blinks | The role `.conf` files were not applied (sysbuild does not forward `-DEXTRA_CONF_FILE`). Rebuild the anchors with `build_all.ps1` (uses `--no-sysbuild` and verifies) and reflash both. See Step 9a. |
| Anchor build stops with `#error Anchor role not configured` | The build did not get a role file. Build with `--no-sysbuild … -- -DEXTRA_CONF_FILE=anchor_a_gateway.conf` (A) or `anchor_b.conf` (B). |
| Arduino: `'Worker' does not name a type` | Old sketch version. Replace `hub_esp32.ino` and add `hub_types.h` from the latest zip (the types were moved into a header because the IDE inserts auto-generated prototypes above any struct defined in the `.ino`). |
| `./build_all.sh` does nothing in PowerShell / `chmod` not found | Those are Linux commands. Use `build_all.ps1` instead (Step 4). |
| `.ps1 cannot be loaded because running scripts is disabled` | Run it as `powershell -ExecutionPolicy Bypass -File .\build_all.ps1`. |
| `'west' not found` | Use the terminal opened from the nRF Connect extension in VS Code. |
| Build fails with very long path errors (nRF5340) | Move the project to a short path such as `D:\ppe_thread`. |
| Anchor build errors about multiprotocol or MPSL | Compare with `nrf/samples/openthread/cli/overlay-multiprotocol.conf` in your NCS version and add any symbol it lists. |
| `BT_LE_ADV_OPT_CONN` undeclared (helmet) | You are on NCS < 3.0. Use `BT_LE_ADV_OPT_CONNECTABLE`, or upgrade. |
| nRF5340 helmet builds but BLE never starts | Check that sysbuild built the network core image (`build/helmet/ipc_radio`), and flash with `west flash` (it flashes both cores). |
| `SB_CONFIG_NETCORE_IPC_RADIO` unknown (helmet) | Older NCS: delete `helmet/sysbuild.conf`. The default network-core image (`hci_ipc`) is fine for a BLE-only helmet. |
| Anchors never form one network | Flash both with `--erase` (an old dataset may be stored). Check that channel, PAN ID and network key match (`ot dataset active`). |
| Vest never connects to the helmet | `CONFIG_PPE_KIT_ID` must match on both. Check the helmet is advertising (log `Advertising as kit 1`). |
| Hub shows "NO RESPONSE" | Check that TX/RX are crossed, GND is shared and the baud rate is 115200. Anchor A logs `hub UART ready`. |
| Extended adverts not received | The vest and anchors scan 1M + Coded. Make sure `CONFIG_BT_CTLR_PHY_CODED=y` took effect. |

## 8. What the bench does *not* yet do (next steps)

| Gap | Production approach (report) |
|---|---|
| Payloads unencrypted (`mic = 0`), fixed Thread key | AES-CCM / Encrypted Advertising Data with per-device keys; Thread joiner commissioning (12.1, 9.4.3) |
| One radio per anchor, time-shared BLE + Thread | Two nRF54L15 + nRF21540 per anchor (9.3) |
| ACK beacon and continuous scanning on the vest | PAwR downlink with ~1 ms listening per interval (9.1) |
| Gateway anchor + UART instead of a border router | Raspberry Pi CM5 + nRF RCP running OpenThread Border Router (10) |
| Sensors are bench parts (MPU-6050, BMP581); head proximity and vital signs are not measured | LSM6DSV16X and a proximity-capacitance sensor (report 5.1). See *Adding real sensors*. |
| No NFC issuance or OTA | NFC out-of-band pairing (7.2); MCUboot + SMP in the charging rack (12) |
| No shoe node | Optional SKU on nRF54L05 (5.2) |
