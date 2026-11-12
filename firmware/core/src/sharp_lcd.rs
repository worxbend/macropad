//! Wire format of the Sharp LS011B7DH03 memory LCD (the nice!view panel).
//!
//! The bytes are meant for an MSB-first SPI bus, mode 0, at most 1 MHz, with chip select
//! held HIGH for the whole frame (this panel's select is active high).

use crate::framebuffer::{Framebuffer, BYTES_PER_ROW, HEIGHT};

const WRITE_LINES: u8 = 0x80;
/// The panel needs its common electrode polarity flipped regularly or the image degrades.
/// EXTMODE is tied low on the nice!view, so the flip travels in this command bit.
const VCOM_HIGH: u8 = 0x40;
const LINE_BYTES: usize = 1 + BYTES_PER_ROW + 1;
/// Command byte, every line (address, pixels, trailer), and the final trailer.
pub const FRAME_BYTES: usize = 1 + HEIGHT * LINE_BYTES + 1;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Orientation {
    Normal,
    /// For a module mounted with its header on the other side.
    Rotated180,
}

pub struct FrameEncoder {
    orientation: Orientation,
    vcom_high: bool,
}

impl FrameEncoder {
    pub const fn new(orientation: Orientation) -> Self {
        Self {
            orientation,
            vcom_high: false,
        }
    }

    /// Encodes a full-screen update and flips VCOM for the next one.
    pub fn encode(&mut self, frame: &Framebuffer) -> [u8; FRAME_BYTES] {
        let mut bytes = [0; FRAME_BYTES];
        bytes[0] = if self.vcom_high {
            WRITE_LINES | VCOM_HIGH
        } else {
            WRITE_LINES
        };
        self.vcom_high = !self.vcom_high;
        let (wire_lines, _final_trailer) = bytes[1..].as_chunks_mut::<LINE_BYTES>();
        for (line, wire_line) in wire_lines.iter_mut().enumerate() {
            // The panel reads line addresses least significant bit first; they count from 1.
            wire_line[0] = (line as u8 + 1).reverse_bits();
            wire_line[1..=BYTES_PER_ROW].copy_from_slice(&self.panel_row(frame, line));
        }
        bytes
    }

    /// One row as the panel wants it: a set bit is a reflective (light) pixel.
    fn panel_row(&self, frame: &Framebuffer, line: usize) -> [u8; BYTES_PER_ROW] {
        match self.orientation {
            Orientation::Normal => frame.row(line).map(|ink| !ink),
            Orientation::Rotated180 => {
                let mut row = frame.row(HEIGHT - 1 - line).map(|ink| !ink.reverse_bits());
                row.reverse();
                row
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::framebuffer::WIDTH;

    fn line(bytes: &[u8; FRAME_BYTES], index: usize) -> &[u8] {
        &bytes[1 + index * LINE_BYTES..][..LINE_BYTES]
    }

    #[test]
    fn frame_is_command_lines_and_trailer() {
        assert_eq!(FRAME_BYTES, 1498);
        let bytes = FrameEncoder::new(Orientation::Normal).encode(&Framebuffer::default());
        assert_eq!(bytes[0], 0x80);
        assert_eq!(bytes[FRAME_BYTES - 1], 0x00);
    }

    #[test]
    fn vcom_bit_alternates_every_frame() {
        let mut encoder = FrameEncoder::new(Orientation::Normal);
        let commands: Vec<u8> = (0..4).map(|_| encoder.encode(&Framebuffer::default())[0]).collect();
        assert_eq!(commands, [0x80, 0xC0, 0x80, 0xC0]);
    }

    #[test]
    fn line_addresses_run_1_to_68_bit_reversed() {
        let bytes = FrameEncoder::new(Orientation::Normal).encode(&Framebuffer::default());
        assert_eq!(line(&bytes, 0)[0], 0b1000_0000);
        assert_eq!(line(&bytes, 1)[0], 0b0100_0000);
        assert_eq!(line(&bytes, 67)[0], 68u8.reverse_bits());
    }

    #[test]
    fn blank_frame_is_all_reflective_with_zero_trailers() {
        let bytes = FrameEncoder::new(Orientation::Normal).encode(&Framebuffer::default());
        for index in 0..HEIGHT {
            assert_eq!(line(&bytes, index)[1..=BYTES_PER_ROW], [0xFF; BYTES_PER_ROW]);
            assert_eq!(line(&bytes, index)[LINE_BYTES - 1], 0x00);
        }
    }

    #[test]
    fn ink_clears_the_matching_wire_bit() {
        let mut frame = Framebuffer::default();
        frame.ink(0, 0);
        frame.ink(15, 2);
        let bytes = FrameEncoder::new(Orientation::Normal).encode(&frame);
        assert_eq!(line(&bytes, 0)[1], 0x7F);
        assert_eq!(line(&bytes, 2)[2], 0xFE);
    }

    #[test]
    fn rotation_moves_the_top_left_pixel_to_the_bottom_right() {
        let mut frame = Framebuffer::default();
        frame.ink(0, 0);
        let bytes = FrameEncoder::new(Orientation::Rotated180).encode(&frame);
        assert_eq!(line(&bytes, HEIGHT - 1)[BYTES_PER_ROW], 0xFE);
        assert_eq!(line(&bytes, 0)[1], 0xFF);
    }

    #[test]
    fn rotating_twice_is_the_identity() {
        let mut frame = Framebuffer::default();
        frame.text(3, 5, "ROTATE");
        frame.ink(WIDTH - 1, 0);
        let rotated = FrameEncoder::new(Orientation::Rotated180).encode(&frame);
        let mut rotated_frame = Framebuffer::default();
        for y in 0..HEIGHT {
            for x in (0..WIDTH).filter(|x| line(&rotated, y)[1 + x / 8] & (0x80 >> (x % 8)) == 0) {
                rotated_frame.ink(x, y);
            }
        }
        let twice = FrameEncoder::new(Orientation::Rotated180).encode(&rotated_frame);
        assert_eq!(twice, FrameEncoder::new(Orientation::Normal).encode(&frame));
    }
}
