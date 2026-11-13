//! A model of the Sharp LS011B7DH03 memory LCD's serial input, written from the datasheet's
//! description and not from the firmware's encoder. Every picture the simulator draws has gone
//! through it, so a wrong bit order or line address in `macropad_core::sharp_lcd` would show.
//!
//! One burst is everything clocked in while chip select is high, first bit first:
//! three mode bits (write, VCOM, clear) and five unused bits; then per line an 8-bit address
//! sent least significant bit first, 160 pixel bits from the left edge (1 is a light pixel),
//! and 8 unused bits; then 8 more unused bits.
//!
//! This is a model of the document, not of a real panel. No panel has been connected.

use std::fmt;

use macropad_core::framebuffer::{Framebuffer, Rect, HEIGHT, WIDTH};

const UNUSED_MODE_BITS: usize = 5;
const ADDRESS_BITS: usize = 8;
const TRAILER_BITS: usize = 8;
const LINE_BITS: usize = ADDRESS_BITS + WIDTH + TRAILER_BITS;

#[derive(Debug, PartialEq, Eq)]
pub enum PanelError {
    /// The burst is not a mode byte, whole lines and one trailer.
    Length(usize),
    /// The write bit is clear or the clear bit is set: not a line update.
    Mode,
    LineAddress(usize),
}

impl fmt::Display for PanelError {
    fn fmt(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Self::Length(bits) => write!(formatter, "{bits} bits is not a whole update"),
            Self::Mode => write!(formatter, "the mode bits do not ask for a line update"),
            Self::LineAddress(address) => write!(formatter, "line address {address} is not 1..={HEIGHT}"),
        }
    }
}

/// The bits of an MSB-first SPI transfer in the order they appear on the wire.
struct WireBits<'a> {
    bytes: &'a [u8],
    position: usize,
}

impl WireBits<'_> {
    fn remaining(&self) -> usize {
        self.bytes.len() * 8 - self.position
    }

    /// Callers check `remaining` first.
    fn take(&mut self) -> bool {
        let bit = self.bytes[self.position / 8] & (0x80 >> (self.position % 8)) != 0;
        self.position += 1;
        bit
    }

    fn skip(&mut self, bits: usize) {
        self.position += bits;
    }
}

/// The panel's pixel memory. Lines that a burst does not address keep their picture.
#[derive(Default)]
pub struct Panel {
    memory: Framebuffer,
}

impl Panel {
    pub fn memory(&self) -> &Framebuffer {
        &self.memory
    }

    /// Takes one chip-select-high burst and returns its VCOM bit.
    pub fn receive(&mut self, burst: &[u8]) -> Result<bool, PanelError> {
        let mut bits = WireBits {
            bytes: burst,
            position: 0,
        };
        let line_bits = bits.remaining().saturating_sub(8 + TRAILER_BITS);
        if bits.remaining() < 8 + TRAILER_BITS || !line_bits.is_multiple_of(LINE_BITS) {
            return Err(PanelError::Length(bits.remaining()));
        }
        let (write, vcom_high, clear) = (bits.take(), bits.take(), bits.take());
        if !write || clear {
            return Err(PanelError::Mode);
        }
        bits.skip(UNUSED_MODE_BITS);
        for _ in 0..line_bits / LINE_BITS {
            self.receive_line(&mut bits)?;
        }
        Ok(vcom_high)
    }

    fn receive_line(&mut self, bits: &mut WireBits) -> Result<(), PanelError> {
        let address = (0..ADDRESS_BITS).fold(0, |address, place| address | usize::from(bits.take()) << place);
        if !(1..=HEIGHT).contains(&address) {
            return Err(PanelError::LineAddress(address));
        }
        let line = address - 1;
        for x in 0..WIDTH {
            let light = bits.take();
            if light == self.memory.has_ink(x, line) {
                self.memory.invert(Rect {
                    x,
                    y: line,
                    width: 1,
                    height: 1,
                });
            }
        }
        bits.skip(TRAILER_BITS);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use macropad_core::sharp_lcd::{FrameEncoder, Orientation, FRAME_BYTES};

    /// A picture with no symmetry: a mirrored, shifted or bit-swapped copy differs from it.
    fn lopsided() -> Framebuffer {
        let mut frame = Framebuffer::default();
        frame.text(3, 2, "LEFT TOP");
        frame.text(90, 55, "END 7");
        frame.ink(WIDTH - 1, 0);
        frame.ink(0, HEIGHT - 1);
        frame
    }

    #[test]
    fn the_firmwares_frame_arrives_as_the_same_picture() {
        let mut panel = Panel::default();
        let burst = FrameEncoder::new(Orientation::Normal).encode(&lopsided());
        assert_eq!(panel.receive(&burst), Ok(false));
        assert!(panel.memory() == &lopsided());
    }

    #[test]
    fn a_rotated_frame_arrives_turned_half_a_turn() {
        let mut panel = Panel::default();
        let burst = FrameEncoder::new(Orientation::Rotated180).encode(&lopsided());
        assert_eq!(panel.receive(&burst), Ok(false));
        let original = lopsided();
        for (x, y) in [(0, 0), (4, 3), (WIDTH - 1, 0), (0, HEIGHT - 1), (95, 57)] {
            assert_eq!(
                panel.memory().has_ink(WIDTH - 1 - x, HEIGHT - 1 - y),
                original.has_ink(x, y),
                "({x}, {y})"
            );
        }
    }

    #[test]
    fn the_vcom_bit_follows_every_second_frame() {
        let mut panel = Panel::default();
        let mut encoder = FrameEncoder::new(Orientation::Normal);
        let seen: Vec<_> = (0..4)
            .map(|_| panel.receive(&encoder.encode(&Framebuffer::default())))
            .collect();
        assert_eq!(seen, [Ok(false), Ok(true), Ok(false), Ok(true)]);
    }

    #[test]
    fn a_burst_of_the_wrong_length_or_mode_is_refused() {
        let mut panel = Panel::default();
        let mut burst = FrameEncoder::new(Orientation::Normal).encode(&Framebuffer::default());
        assert_eq!(
            panel.receive(&burst[..FRAME_BYTES - 1]),
            Err(PanelError::Length((FRAME_BYTES - 1) * 8))
        );
        burst[0] = 0x20;
        assert_eq!(panel.receive(&burst), Err(PanelError::Mode));
    }

    #[test]
    fn a_line_address_outside_the_panel_is_refused() {
        let mut panel = Panel::default();
        let mut burst = FrameEncoder::new(Orientation::Normal).encode(&Framebuffer::default());
        burst[1] = 69u8.reverse_bits();
        assert_eq!(panel.receive(&burst), Err(PanelError::LineAddress(69)));
    }
}
