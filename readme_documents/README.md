# Smart PPE Ecosystem – Test Bench Firmware

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

The helmet has no real sensors, so its buttons stand in for them (BTN1 = put on / take off).

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

# Adding real sensors (TTP223, MPU-6050, MAX30102)

The helmet and vest firmware detect real sensors **automatically at boot**. Anything that is wired and answers is used. Anything missing keeps working in simulation, so you can add sensors one at a time.

| Sensor | Goes on | What it does here | Interface |
|---|---|---|---|
| **TTP223** touch module (3 pins) | Helmet (and optionally the vest) | Helmet: head proximity, with the pad behind the foam. Vest: "vest is being worn". | Digital pin |
| **MPU-6050** (GY-521) | **Vest** (optionally a second one on the helmet) | Vest: real falls, posture, man-down. Helmet: head impacts and helmet motion. | I2C |
| **MAX30102** | Helmet | **Non-contact IR proximity** (head present). Heart rate / SpO₂ **only with skin contact**, experimental. | I2C |

If you have only one of each, use: **MPU-6050 → vest, TTP223 → helmet, MAX30102 → helmet.**

> **MAX30102 and the "no skin contact" rule.** Heart rate and SpO₂ from a MAX30102 need the sensor pressed against skin, which the project's hard constraint forbids (report section 2.3). The firmware therefore uses it mainly as a contact-free IR proximity sensor. HR/SpO₂ appear only when something is pressed on it, and the dashboard labels them *experimental*. The SpO₂ value uses an uncalibrated textbook formula and is **not medical-grade**.

## S1 – Check the I/O voltage BEFORE wiring

The sensor modules pull their signal lines up to about 3.3 V. The nRF pins must run at a similar voltage, or they are overdriven.

| Board | What to do |
|---|---|
| **nRF54L15 DK (vest)** | Its I/O runs at **1.8 V by default**. Open *nRF Connect for Desktop → Board Configurator*, select the DK and set **VDD to 3.3 V**. Then write the configuration. |
| **nRF5340 DK (helmet)** | Measure the **VDD** header pin against GND with a multimeter. It should read about **3 V**. If it reads 1.8 V, change the DK's VDD setting (switch or Board Configurator, depending on the board revision) before wiring. |

Power every module from the DK's **VDD** pin and **GND**, **never from 5 V**.

## S2 – Wire the helmet (nRF5340 DK)

| Module pin | nRF5340 DK pin |
|---|---|
| TTP223 **SIG / I/O** | **P1.06** (Arduino D4) |
| TTP223 **VCC** / **GND** | VDD / GND |
| MAX30102 **SDA** | **P1.02** (Arduino SDA) |
| MAX30102 **SCL** | **P1.03** (Arduino SCL) |
| MAX30102 **VIN** / **GND** | VDD / GND |
| *(optional)* second MPU-6050 **SDA / SCL** | same P1.02 / P1.03 (shared I2C bus) |
| *(optional)* second MPU-6050 **VCC / GND** | VDD / GND |

Leave the MAX30102 **INT** pin unconnected (the firmware polls).

**Mounting idea:** put the TTP223 pad and the MAX30102 *behind* a thin layer of the helmet foam, facing the head. The TTP223 detects through a few millimetres of plastic or foam. The MAX30102 sees the head by reflected IR at about 1–2 cm.

## S3 – Wire the vest (nRF54L15 DK)

| Module pin | nRF54L15 DK pin |
|---|---|
| MPU-6050 **SCL** | **P1.11** |
| MPU-6050 **SDA** | **P1.12** |
| MPU-6050 **VCC** / **GND** | VDD / GND |
| MPU-6050 **AD0** | leave open / GND → address 0x68 |
| *(optional)* TTP223 **SIG** | **P1.15** |
| *(optional)* TTP223 **VCC** / **GND** | VDD / GND |

**Mounting:** tape the MPU-6050 firmly to the DK (or to the vest), so they move together. The orientation doesn't matter, because the firmware learns "upright" at boot.

The pins are set in `vest/boards/nrf54l15dk_nrf54l15_cpuapp.overlay` and `helmet/boards/nrf5340dk_nrf5340_cpuapp.overlay`. Change them there if a pin is taken on your board revision.

## S4 – Rebuild and flash helmet, vest and hub

**The anchors do not need to change.** The real-sensor data travels in 4 bytes the anchors already forward untouched.

```powershell
powershell -ExecutionPolicy Bypass -File .\build_all.ps1 -Flash -Only vest   -SnVest   <vest-serial>
powershell -ExecutionPolicy Bypass -File .\build_all.ps1 -Flash -Only helmet -SnHelmet <helmet-serial>
```

Then re-upload `hub_esp32.ino` from Arduino IDE (the folder's `ppe_proto.h` was updated too). Helmet and vest must be updated **together**, because the helmet → vest status message grew.

## S5 – Check what was detected (boot log)

**Helmet**, for example:
```
TTP223 touch input on pin 6: REAL head-proximity sensor
MAX30102 found: REAL IR proximity (HR/SpO2 only on skin contact - experimental)
IR baseline: measuring for 2 s - keep the sensor clear
No helmet MPU-6050: impacts via button 2, motion simulated
```

**Vest**, for example:
```
vest presence: simulated (always worn)
MPU-6050 (WHO_AM_I 0x68) at 0x68: REAL motion, +/-16 g. Keep the vest upright for the first second ...
```

A line like `WHO_AM_I 0x70 … clone … continuing` is fine. Many "MPU-6050" boards carry a compatible clone chip.

The dashboard's **Real sensors** column lists what each worker is actually using, for example `vest-IMU helmet-touch helmet-IR`.

## S6 – Calibrate

1. **Helmet IR baseline.** The MAX30102 measures "nothing in front" for 2 s after boot, so power the helmet **with nothing near the sensor**. To redo it later, take the helmet off and **hold helmet BTN4 for 2 s**.
2. **Helmet IR threshold.** Every 2 s the helmet logs a line like `sensors: touch=1 ir=21450 base=1800 prox=63 near=1 …`. Note the `ir` value with the helmet on and off. Set `CONFIG_PPE_IR_PROX_ON` to a value between the two "minus `base`" levels. To set it, add a line such as `CONFIG_PPE_IR_PROX_ON=8000` to `helmet/prj.conf` and rebuild. The default is 3000.
3. **TTP223 power-up.** The TTP223 calibrates itself when it powers up. Reset the DK with **nothing touching the pad**.
4. **Vest "upright".** The firmware treats the orientation 1 s after boot as "standing". Hold the vest in its normal standing orientation at boot, or later hold it upright and **hold vest BUTTON 3 for 2 s**.

## S7 – Tests with real sensors

| # | Test | What to do | Expected |
|---|---|---|---|
| R1 | **Head proximity** | Put a hand (or the helmet on your head) over the TTP223 pad **and** in front of the MAX30102 | After 3 s the helmet is `worn`: LED2 on, and LED4 on (IR sees something close) |
| R2 | **Removal** | Take it away | After 5 s `NOT WORN`, then the vest raises `HELMET_OFF` about 10 s later |
| R3 | **Spoof, now real** | Touch **only** the TTP223 pad, keeping the IR sensor clear | `uncertain` (LED2 blinks), never `worn`. Touch alone is not enough. |
| R4 | **Real fall** | Tape the MPU-6050 to the vest DK. Drop the pair from 0.5–1 m onto a folded towel on a table, so it lands **on its side** | `FALL candidate … (estimated from free-fall time)`, then the pre-alert, then `FALL` at the hub. From about 1.5 m or more it becomes `FALL_FROM_HEIGHT`. |
| R5 | **No false alarm** | Shake, tap or tilt the board without dropping it | No fall candidate |
| R6 | **Real man-down** | Calibrate upright (S6.4), then lay the board flat and keep it still | After 20 s the "ARE YOU OK?" prompt, then `MAN_DOWN` if you don't answer |
| R7 | **Head impact** (helmet IMU) | Knock the helmet MPU-6050 sharply on the table | `IMU: head impact … mg`. The vest raises `HEAD_IMPACT`. |
| R8 | **PPG, experimental** | Rest a fingertip lightly and still on the MAX30102 for 10–15 s | Helmet LED4 blinks (contact). The log, then the dashboard **Vitals** column, show `HR …, SpO2 …% (experimental)`. |

**Safety notes on the drop test:** use a soft landing, keep cable lengths short, and never drop the board onto hard floors.

## S8 – Troubleshooting real sensors

| Symptom | Fix |
|---|---|
| `MAX30102 not found` / `No MPU-6050 found` | Check SDA/SCL aren't swapped, GND is shared, and the module has VDD power. Check the DK's VDD (S1). For an MPU-6050 with AD0 high, set `CONFIG_PPE_MPU6050_ADDR=0x69`. |
| MAX30102 not found on a purple / generic board | Many cheap MAX30102 boards pull SDA/SCL up to **1.8 V**, which a 3 V nRF may not read reliably. Move the board's pull-up jumper or pads to 3.3 V, or add 4.7 kΩ pull-ups from SDA and SCL to VDD. |
| `MPU-6050 read failed (N errors)` at run time | A loose jumper wire. The firmware holds the last good sample, so a wire glitch never fakes a posture change. Re-seat the wires. |
| Build error mentioning `i2c22`, `i2c1` or a pin conflict | Your board revision uses that pin or peripheral. Change the pins or the I2C instance in the board overlay (S3). |
| Helmet goes `NOT WORN` after about 1–2 minutes of continuous wear, with touch only | Some TTP223 modules drop a long continuous touch when they re-calibrate. With the MAX30102 also fitted, the firmware keeps `worn` while the IR still sees the head. The production design uses a true proximity-capacitance sensor (report 5.2). |
| Fall not detected in R4 | The landing was too soft (impact < 3 g) or it landed upright (tilt < 60°). Use a firmer towel and let it land on its side. Thresholds are in `vest/src/fall_detect.h`. |
| HR shows nothing | Keep the finger very still with light pressure. Check `contact=1` in the helmet log, and if not, lower `CONFIG_PPE_IR_CONTACT`. |

## S9 – What is still simulated or approximate

- **Fall height.** There is **no barometer**, so the fall height is **estimated from free-fall time** (h = g·t²/2). A BMP581 would add the measured height drop (report 5.3).
- **Thermopile.** There is **no thermopile**, so the MAX30102 replaces the "warm object" signal with reflected-IR proximity. It cannot measure temperature.
- **TTP223.** This is a touch sensor with limited range through material, not a true proximity sensor.
- **Helmet "motion".** This is the helmet's own movement, not a true correlation with the vest's movement.



---

# On-body detection by motion matching (helmet IMU vs vest IMU)

When **both** the helmet and the vest have an MPU-6050, the vest checks whether the two move **together**, which says whether each item is actually on the worker's body. No skin contact is needed. The algorithm is the same one as in the body-motion lab (`common/sensors/motion_features.c` and `fusion.c`), now built into the PPE firmware.

## How it runs

| Board | What it does |
|---|---|
| Helmet | Reads its IMU at 50 Hz (accelerometer + gyro). Every 1.92 s it makes a 20-byte motion summary: motion level, step rhythm, rotation and motion shape. It notifies the summary to the vest on a second GATT characteristic of the helmet service |
| Vest | Makes the same summary from its own IMU (`vest/src/onbody.c`), compares the two, and raises events |

| Situation | Event at the hub | Priority |
|---|---|---|
| Vest moving, helmet still for 10 s | `HELMET_NOT_ON_BODY` | P1 |
| Helmet moving but swinging (> 80 °/s) or out of step for 10 s | `HELMET_CARRIED` | P2 |
| Helmet moving, vest still for 10 s | `VEST_NOT_ON_BODY` | P1 |

While a condition lasts, its alert bit stays set in every heartbeat. These are the last three free bits of the alert mask, so the hub's *Active alerts* column shows them.

## When it runs

The matching is active only while all of the following are true. Otherwise it is off, and the vest log says why.

- The BAN link is up.
- The vest has subscribed to the helmet's motion summaries.
- **Both** boards have a real MPU-6050 (simulated motion is never compared).

**Both still means no decision:** a helmet on a table while the worker stands still looks the same as a worn helmet. The motion matching therefore complements the helmet's own wear sensors (TTP223 / MAX30102); it does not replace them.

## What to update

1. Flash the **helmet**, **vest** and **hub** (new event names). The anchors need a rebuild only if you want SystemView on them; the uplink format did not change.
2. Wire an MPU-6050 to the helmet as in section S2 (shared I2C bus with the MAX30102), and keep the vest's MPU-6050 as in S3.

## Tuning

Thresholds are in `vest/Kconfig`; override them in `vest/prj.conf`:

| Option | Default |
|---|---|
| `CONFIG_PPE_BM_MOVE_MG` | 30 |
| `CONFIG_PPE_BM_STILL_MG` | 10 |
| `CONFIG_PPE_BM_OFF_AFTER_S` | 10 |
| `CONFIG_PPE_BM_BOTH_STILL_S` | 60 |
| `CONFIG_PPE_BM_MISMATCH_S` | 10 |
| `CONFIG_PPE_BM_CADENCE_TOL_X100` | 25 |
| `CONFIG_PPE_BM_MATCH_MIN_PCT` | 50 |
| `CONFIG_PPE_BM_SWING_DPS` | 80 |

Set the `onbody` log module to `LOG_LEVEL_DBG` in `vest/src/onbody.c` to see both boards' numbers every 1.92 s while you tune.

**PC test** of the algorithm (8 scenarios: walking, helmet on a table, carried, vest on a chair, standing, both put down, out of range, the "both still" limit):

```bash
cd tests
gcc -O2 -I../common/sensors -I. test_body_motion.c ../common/sensors/motion_features.c ../common/sensors/fusion.c sim_motion.c -lm -o tb && ./tb
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
| Sensor poll | Helmet | The 20 ms touch / IR / IMU poll |
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
- **BTN4:** spoof test (a hand inside the helmet on a table). **Hold 2 s:** re-measure the IR baseline (helmet off).
- **LED1:** linked. **LED2:** worn (blinks = uncertain). **LED3:** impact. **LED4:** something is close to the IR sensor (blinks = skin contact).

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
gcc -O2 -I../common/sensors test_ppg.c ../common/sensors/ppg.c -lm -o tp && ./tp
```

This runs the heart-rate / SpO₂ algorithm on synthetic PPG signals (52–110 bpm, noise, no-contact case).

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
| Sensors are bench parts (TTP223, MPU-6050, MAX30102) or simulated | LSM6DSV16X, BMP581, MLX90632 and a proximity-capacitance sensor (report 5.1). See *Adding real sensors*. |
| No NFC issuance or OTA | NFC out-of-band pairing (7.2); MCUboot + SMP in the charging rack (12) |
| No shoe node | Optional SKU on nRF54L05 (5.2) |
