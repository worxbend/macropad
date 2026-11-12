# Parts and sourcing

Stock and library type come from the JLCPCB parts search on 2026-11-12. Stock moves fast: check again before ordering.
"Basic" parts have no setup fee at JLCPCB. "Extended" parts cost a one-time fee per distinct part.

## Machine-placed (JLCPCB assembly, bottom face)

| Part | Value | Qty | JLCPCB # | Type | Stock | Why this one |
|---|---|---|---|---|---|---|
| MCU | RP2354A, QFN-60 | 1 | C41378174 | Extended | 1 448 | RP2350 with flash inside: no flash chip, no QSPI routing |
| Regulator inductor | AOTA-B201610S3R3-101-T, 3.3 µH | 1 | C42411119 | Extended | 810 | The part Raspberry Pi specifies for the on-chip 1.1 V regulator |
| Crystal | X322512MSB4SI, 12 MHz, 3225 | 1 | C9002 | Basic | 495 199 | See the crystal note below |
| 3.3 V regulator | AP2112K-3.3, SOT-23-5 | 1 | C51118 | Extended | 5 795 | 600 mA, stable with small ceramic capacitors |
| USB ESD | USBLC6-2SC6 | 1 | C7519 | Extended | 45 001 | |
| Level shifter | 74LVC1T45, SOT-26 | 1 | C168856 | Extended | 45 825 | 3.3 V data to the 5 V LEDs |
| USB-C | TYPE-C-31-M-12, 16 pin | 1 | C165948 | Extended | 544 338 | |
| Fuse | nSMD050, 1206, 500 mA | 1 | C69688 | Extended | 20 188 | Resettable |
| Buttons | TS-1187A | 2 | C318884 | Basic | 828 738 | BOOT and RESET |
| RGB LED | SK6812SIDE-A, 4 x 1.6 mm | 8 | C5378721 | Extended | 111 190 | Side-emitting: shines out of the PCB edge |
| Hot-swap socket | Kailh CPG151101S11-2 | 12 | C49352235 | Extended | 29 766 | |
| Capacitor | 100 nF 0402 | 20 | C1525 | Basic | 33 M | |
| Capacitor | 1 µF 0402 | 1 | C52923 | Basic | 10 M | |
| Capacitor | 4.7 µF 0402 | 4 | C23733 | Basic | 717 287 | |
| Capacitor | 10 µF 0603 | 4 | C19702 | Basic | 9.8 M | |
| Capacitor | 15 pF C0G 0402 | 2 | C1548 | Basic | 1 M | |
| Resistor | 1 kΩ 0402 | 2 | C11702 | Basic | 32 M | |
| Resistor | 10 kΩ 0402 | 1 | C25744 | Basic | 22 M | |
| Resistor | 5.1 kΩ 0402 | 2 | C25905 | Basic | 4 M | USB-C CC pull-downs |
| Resistor | 27 Ω 0402 | 2 | C25100 | Extended | 665 508 | USB series resistors |
| Resistor | 33 Ω 0402 | 1 | C25105 | Basic | 3.5 M | |

## Hand-soldered (through-hole, top face)

| Part | Qty | JLCPCB # | Note |
|---|---|---|---|
| Alps EC11E18244AU encoder | 2 | C202365 | 2 553 in stock. JLCPCB can also place it as a through-hole part. |
| 1 x 5 socket, 2.54 mm | 1 | C50950 | For the nice!view. Use the low-profile sockets that ship with the display if you have them. |
| nice!view | 1 | not at JLCPCB | From keyboard shops (Typeractive, splitkb, and others). |
| MX switches and keycaps | 12 | not at JLCPCB | |

## Substitutions I made, and what to check

1. **Crystal.** Raspberry Pi's design uses the Abracon ABM8-272-T3 (C20625731). JLCPCB had 1 piece.
   The board uses the common X322512MSB4SI with 15 pF load capacitors and the same 1 kΩ series resistor.
   Its rated load is 20 pF, so it will run slightly fast: far inside the USB tolerance, but this pairing
   is not from the Raspberry Pi guide. If USB does not enumerate on the first boards, look here first.
2. **RP2354A instead of RP2350A plus flash.** Stock was 1 448 against 5 840 for the RP2350A (C42411118).
   If the RP2354A runs out, the RP2350A needs an external flash chip and a board change.
3. **Hot-swap socket.** The plain CPG151101S11 (C2803348) had zero stock; the `-2` variant is the same socket.
4. **Inductor polarity.** The AOTA inductor has a marked end. Confirm against "Hardware design with RP2350"
   that the marked end faces VREG_LX, and check its rotation in JLCPCB's preview.

## PCBWay

PCBWay has no fixed parts library. Their turnkey assembly buys from distributors, so every part above can be
sourced, including the ABM8-272-T3 crystal. Send them the same Gerbers, BOM and placement list; they quote
parts per order. It usually costs more than JLCPCB for a board this small and takes longer.

## Board order settings

4 layers, 1.6 mm, any colour, HASL or ENIG (ENIG is kinder to the 0.4 mm pitch QFN).
Assembly on the bottom side only. Minimum track and gap on the board: 0.15 mm. Smallest drill: 0.3 mm.
