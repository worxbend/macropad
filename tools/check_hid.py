#!/usr/bin/env python3
"""Fail when the USB HID report descriptors disagree with the reports the firmware sends.

The descriptors in firmware/fw/src/usb.rs are hand-written bytes. A host trusts them: if they
describe 7 bytes and the firmware sends 8, keys do the wrong thing or nothing at all. This script
parses the bytes the way a host does (HID 1.11, section 6.2.2) and compares the result with the
report sizes in usb.rs and the codes in firmware/core/src/hid.rs.

It reads source files only. Nothing here has been tried against a real host.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
USB_RS = REPO / "firmware" / "fw" / "src" / "usb.rs"
HID_RS = REPO / "firmware" / "core" / "src" / "hid.rs"

# Item prefixes with the two size bits masked off (HID 1.11, 6.2.2.4 to 6.2.2.8).
INPUT, OUTPUT, COLLECTION, END_COLLECTION = 0x80, 0x90, 0xA0, 0xC0
USAGE_PAGE, LOGICAL_MINIMUM, LOGICAL_MAXIMUM = 0x04, 0x14, 0x24
REPORT_SIZE, REPORT_ID, REPORT_COUNT = 0x74, 0x84, 0x94
USAGE, USAGE_MINIMUM, USAGE_MAXIMUM = 0x08, 0x18, 0x28
DATA_SIZES = (0, 1, 2, 4)
CONSTANT_BIT, VARIABLE_BIT = 0x01, 0x02

PAGE_GENERIC_DESKTOP, PAGE_KEYBOARD, PAGE_LEDS, PAGE_CONSUMER = 0x01, 0x07, 0x08, 0x0C
FIRST_MODIFIER_USAGE, LAST_MODIFIER_USAGE = 0xE0, 0xE7
LOCK_LEDS = 5


@dataclass
class Field:
    """One Input or Output item: `count` fields of `size` bits."""

    direction: int
    flags: int
    page: int
    size: int
    count: int
    logical_maximum: int
    usage_minimum: int | None
    usage_maximum: int | None

    @property
    def bits(self) -> int:
        return self.size * self.count

    @property
    def is_padding(self) -> bool:
        return bool(self.flags & CONSTANT_BIT)

    @property
    def is_array(self) -> bool:
        return not self.flags & (CONSTANT_BIT | VARIABLE_BIT)


@dataclass
class Descriptor:
    fields: list[Field] = field(default_factory=list)
    application: tuple[int, int] | None = None
    open_collections: int = 0
    has_report_id: bool = False

    def report_bits(self, direction: int) -> int:
        return sum(item.bits for item in self.fields if item.direction == direction)

    def data_fields(self, direction: int) -> list[Field]:
        return [item for item in self.fields if item.direction == direction and not item.is_padding]


def items(descriptor: list[int]):
    """Yields (prefix without size bits, value) for each short item."""
    position = 0
    while position < len(descriptor):
        prefix = descriptor[position]
        size = DATA_SIZES[prefix & 0x03]
        data = descriptor[position + 1 : position + 1 + size]
        if len(data) != size:
            raise ValueError(f"item at byte {position} runs past the end of the descriptor")
        yield prefix & 0xFC, int.from_bytes(bytes(data), "little")
        position += 1 + size


def parse(descriptor: list[int]) -> Descriptor:
    """Walks the items with the global and local state a host keeps."""
    parsed = Descriptor()
    state: dict[int, int] = {}
    usages: dict[int, int] = {}
    for tag, value in items(descriptor):
        if tag in (INPUT, OUTPUT):
            parsed.fields.append(
                Field(
                    direction=tag,
                    flags=value,
                    page=state.get(USAGE_PAGE, 0),
                    size=state.get(REPORT_SIZE, 0),
                    count=state.get(REPORT_COUNT, 0),
                    logical_maximum=state.get(LOGICAL_MAXIMUM, 0),
                    usage_minimum=usages.get(USAGE_MINIMUM),
                    usage_maximum=usages.get(USAGE_MAXIMUM),
                )
            )
            usages = {}
        elif tag == COLLECTION:
            if parsed.open_collections == 0:
                parsed.application = (state.get(USAGE_PAGE, 0), usages.get(USAGE, 0))
            parsed.open_collections += 1
            usages = {}
        elif tag == END_COLLECTION:
            parsed.open_collections -= 1
        elif tag in (USAGE, USAGE_MINIMUM, USAGE_MAXIMUM):
            usages[tag] = value
        else:
            parsed.has_report_id |= tag == REPORT_ID
            state[tag] = value
    return parsed


def byte_array(source: str, name: str) -> list[int]:
    """The bytes of `const NAME: [u8; N] = [...]`, after checking N."""
    declaration = re.search(rf"const {name}: \[u8; (\d+)\] = \[(.*?)\];", source, re.DOTALL)
    if declaration is None:
        raise ValueError(f"no `const {name}` byte array in usb.rs")
    values = [int(literal, 16) for literal in re.findall(r"0x([0-9A-Fa-f]{2})\b", declaration.group(2))]
    if len(values) != int(declaration.group(1)):
        raise ValueError(f"{name} declares {declaration.group(1)} bytes and lists {len(values)}")
    return values


def constant(source: str, name: str) -> int:
    declaration = re.search(rf"const {name}: \w+ = (0x[0-9A-Fa-f_]+|[\d_]+);", source)
    if declaration is None:
        raise ValueError(f"no `const {name}`")
    return int(declaration.group(1).replace("_", ""), 0)


def key_codes(hid_rs: str) -> list[int]:
    """Every code in `pub mod key`."""
    module = re.search(r"pub mod key \{(.*?)\n\}", hid_rs, re.DOTALL)
    if module is None:
        raise ValueError("no `pub mod key` in hid.rs")
    return [int(code, 16) for code in re.findall(r": u8 = 0x([0-9A-Fa-f]{2});", module.group(1))]


def shape_problems(name: str, parsed: Descriptor, application: tuple[int, int]) -> list[str]:
    problems = []
    if parsed.application != application:
        problems.append(f"{name}: application collection is {parsed.application}, expected {application}")
    if parsed.open_collections != 0:
        problems.append(f"{name}: collections are not balanced")
    if parsed.has_report_id:
        problems.append(f"{name}: has a report ID, but the firmware sends reports without one")
    return problems


def keyboard_problems(parsed: Descriptor, usb_rs: str, hid_rs: str) -> list[str]:
    problems = shape_problems("keyboard", parsed, (PAGE_GENERIC_DESKTOP, 0x06))
    report_bytes, lock_bytes = constant(usb_rs, "KEYBOARD_REPORT_BYTES"), constant(usb_rs, "LOCK_REPORT_BYTES")
    if parsed.report_bits(INPUT) != report_bytes * 8:
        problems.append(f"keyboard: input report is {parsed.report_bits(INPUT)} bits, firmware sends {report_bytes} bytes")
    if parsed.report_bits(OUTPUT) != lock_bytes * 8:
        problems.append(f"keyboard: output report is {parsed.report_bits(OUTPUT)} bits, firmware reads {lock_bytes} byte")
    inputs, outputs = parsed.data_fields(INPUT), parsed.data_fields(OUTPUT)
    if len(inputs) != 2 or len(outputs) != 1:
        return problems + ["keyboard: expected modifier bits, a key array and one LED field"]
    modifiers, keys, leds = inputs[0], inputs[1], outputs[0]
    modifier_range = (modifiers.usage_minimum, modifiers.usage_maximum)
    if (modifiers.page, modifiers.bits, modifier_range) != (PAGE_KEYBOARD, 8, (FIRST_MODIFIER_USAGE, LAST_MODIFIER_USAGE)):
        problems.append("keyboard: the first byte is not the eight modifier bits 0xE0..0xE7")
    if parsed.fields[1].bits != 8 or not parsed.fields[1].is_padding:
        problems.append("keyboard: the second byte is not the reserved byte of the boot report")
    rollover = constant(hid_rs, "ROLLOVER")
    if not keys.is_array or (keys.page, keys.size, keys.count) != (PAGE_KEYBOARD, 8, rollover):
        problems.append(f"keyboard: the key array is not {rollover} bytes of keyboard usages")
    highest = max(key_codes(hid_rs))
    if min(keys.logical_maximum, keys.usage_maximum or 0) < highest:
        problems.append(f"keyboard: hid.rs has key code {highest:#04x}, above what the key array declares")
    if (leds.page, leds.bits, leds.usage_minimum) != (PAGE_LEDS, LOCK_LEDS, 1):
        problems.append("keyboard: the output field is not the five lock LEDs starting at num lock")
    return problems


def consumer_problems(parsed: Descriptor, usb_rs: str, hid_rs: str) -> list[str]:
    problems = shape_problems("consumer", parsed, (PAGE_CONSUMER, 0x01))
    report_bytes = constant(usb_rs, "CONSUMER_REPORT_BYTES")
    if parsed.report_bits(INPUT) != report_bytes * 8 or parsed.report_bits(OUTPUT) != 0:
        problems.append(f"consumer: input report is {parsed.report_bits(INPUT)} bits, firmware sends {report_bytes} bytes")
    inputs = parsed.data_fields(INPUT)
    if len(inputs) != 1 or not inputs[0].is_array or inputs[0].page != PAGE_CONSUMER:
        return problems + ["consumer: expected one array field of consumer usages"]
    highest = constant(hid_rs, "MAX_USAGE")
    if (inputs[0].logical_maximum, inputs[0].usage_maximum) != (highest, highest):
        problems.append(f"consumer: descriptor allows usages up to {inputs[0].logical_maximum:#06x}, hid.rs says {highest:#06x}")
    return problems


def main() -> int:
    try:
        usb_rs, hid_rs = USB_RS.read_text(), HID_RS.read_text()
        keyboard = parse(byte_array(usb_rs, "KEYBOARD_DESCRIPTOR"))
        consumer = parse(byte_array(usb_rs, "CONSUMER_DESCRIPTOR"))
        problems = keyboard_problems(keyboard, usb_rs, hid_rs) + consumer_problems(consumer, usb_rs, hid_rs)
    except (ValueError, OSError) as error:
        print(f"check_hid: cannot read the firmware sources: {error}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"check_hid: {problem}", file=sys.stderr)
    if not problems:
        print(
            f"check_hid: keyboard descriptor is an {keyboard.report_bits(INPUT) // 8}-byte boot report "
            f"with a {keyboard.report_bits(OUTPUT) // 8}-byte lock LED report"
        )
        print(f"check_hid: consumer descriptor is one {consumer.report_bits(INPUT)}-bit usage; both match the firmware")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
