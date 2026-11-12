# Hardware notes

## How it compares to macropad-nyxilab

| | nyxilab | this board |
|---|---|---|
| Size | 159 x 98 mm | 89.6 x 88.1 mm |
| Wiring | Hand-wired matrix with diodes | 4-layer PCB, one GPIO per key |
| Brain | Pico 2 board | Bare RP2354A on the PCB |
| Keys | 12 MX | 12 MX, hot-swap |
| Centre control | Thumbstick or one knob | Two knobs |
| Screens | Two colour ST7789 | One nice!view (monochrome, always-on, sunlight readable) |
| Light | 16 LEDs on the base | 8 side-emitting LEDs behind strips in the case sides |
| Firmware | C++ / PlatformIO | Rust / embassy |

## Layout

Top view, USB at the back:

```
+---------------------------------------------+
|  (knob)   [   nice!view    ]      (knob)    |   back zone, 22 mm deep
|  [K0]     [K1]     [K2]     [K3]            |
|  [K4]     [K5]     [K6]     [K7]            |   19.05 mm pitch
|  [K8]     [K9]     [K10]    [K11]           |
+---------------------------------------------+
   LEDs on both side edges, four per side
```

The MCU, USB-C port, regulator, crystal and both buttons sit on the bottom face under the display.

## Circuit, in words

- **USB-C**: 5.1 kΩ on both CC pins, USBLC6 ESD diodes, 27 Ω series resistors, 500 mA resettable fuse.
- **Power**: VBUS through the fuse is the 5 V rail (LEDs, level shifter). An AP2112K makes 3.3 V.
  The RP2354A makes its own 1.1 V core supply with the on-chip switching regulator and L1.
- **Clock**: 12 MHz crystal with a 1 kΩ series resistor on XOUT.
- **Flashing**: BOOT pulls QSPI_SS low through 1 kΩ, which starts the ROM USB bootloader. RESET pulls RUN low.
  SWCLK, SWDIO and GND are on three test pads next to the MCU.
- **Keys and knobs**: each switch connects one GPIO to ground. The firmware turns on the internal pull-ups.
- **Display**: SPI0 (SCK GPIO22, MOSI GPIO23), chip select GPIO24, active high.
- **LEDs**: GPIO9, through a 74LVC1T45 to 5 V logic, then eight SK6812 in a chain: right side back to front,
  then left side front to back. The firmware caps total LED current at about 200 mA.

Pin numbers live in `board.toml`. The full netlist is `pcb/netlist.txt`.

## Layer stack

| Layer | Use |
|---|---|
| F.Cu | Signals, ground pour |
| In1.Cu | Ground plane |
| In2.Cu | 5 V plane, with a 3.3 V island under the MCU and the display socket |
| B.Cu | Parts, signals, ground pour |

## Spare pins

GPIO10 to GPIO15, GPIO25 and GPIO26 are unconnected. They have no pads; adding a header means a board change.
