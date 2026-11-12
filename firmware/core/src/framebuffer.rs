//! 1-bit framebuffer the size of the nice!view panel.

use crate::font::{glyph, ADVANCE, GLYPH_HEIGHT};

pub const WIDTH: usize = 160;
pub const HEIGHT: usize = 68;
pub const BYTES_PER_ROW: usize = WIDTH / 8;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rect {
    pub x: usize,
    pub y: usize,
    pub width: usize,
    pub height: usize,
}

/// A set bit is ink (a dark pixel). The most significant bit of a byte is its leftmost pixel.
#[derive(Clone, PartialEq, Eq)]
pub struct Framebuffer {
    rows: [[u8; BYTES_PER_ROW]; HEIGHT],
}

impl Default for Framebuffer {
    fn default() -> Self {
        Self {
            rows: [[0; BYTES_PER_ROW]; HEIGHT],
        }
    }
}

impl Framebuffer {
    pub fn row(&self, y: usize) -> &[u8; BYTES_PER_ROW] {
        &self.rows[y]
    }

    pub fn has_ink(&self, x: usize, y: usize) -> bool {
        self.rows[y][x / 8] & pixel_mask(x) != 0
    }

    /// Darkens one pixel. Pixels outside the panel are clipped, as in any raster drawing.
    pub fn ink(&mut self, x: usize, y: usize) {
        if x < WIDTH && y < HEIGHT {
            self.rows[y][x / 8] |= pixel_mask(x);
        }
    }

    pub fn invert(&mut self, area: Rect) {
        for y in area.y..(area.y + area.height).min(HEIGHT) {
            for x in area.x..(area.x + area.width).min(WIDTH) {
                self.rows[y][x / 8] ^= pixel_mask(x);
            }
        }
    }

    pub fn horizontal_line(&mut self, y: usize) {
        (0..WIDTH).for_each(|x| self.ink(x, y));
    }

    /// Draws a bar `height` pixels tall that stands on row `bottom_y`.
    pub fn bar(&mut self, x: usize, bottom_y: usize, height: usize) {
        (0..height).for_each(|rise| self.ink(x, bottom_y - rise));
    }

    /// Draws text with its top-left corner at (`x`, `y`).
    pub fn text(&mut self, x: usize, y: usize, text: &str) {
        for (index, character) in text.chars().enumerate() {
            self.glyph(x + index * ADVANCE, y, character);
        }
    }

    fn glyph(&mut self, x: usize, y: usize, character: char) {
        for (column, bits) in glyph(character).into_iter().enumerate() {
            for row in (0..GLYPH_HEIGHT).filter(|row| bits & (1 << row) != 0) {
                self.ink(x + column, y + row);
            }
        }
    }
}

fn pixel_mask(x: usize) -> u8 {
    0x80 >> (x % 8)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ink_count(frame: &Framebuffer) -> u32 {
        (0..HEIGHT)
            .flat_map(|y| frame.row(y).iter())
            .map(|byte| byte.count_ones())
            .sum()
    }

    #[test]
    fn leftmost_pixel_is_the_most_significant_bit() {
        let mut frame = Framebuffer::default();
        frame.ink(0, 0);
        frame.ink(9, 0);
        assert_eq!(frame.row(0)[..2], [0x80, 0x40]);
    }

    #[test]
    fn corners_are_addressable_and_outside_is_clipped() {
        let mut frame = Framebuffer::default();
        frame.ink(WIDTH - 1, HEIGHT - 1);
        frame.ink(WIDTH, 0);
        frame.ink(0, HEIGHT);
        assert!(frame.has_ink(WIDTH - 1, HEIGHT - 1));
        assert_eq!(ink_count(&frame), 1);
    }

    #[test]
    fn invert_flips_exactly_the_area() {
        let mut frame = Framebuffer::default();
        frame.ink(1, 1);
        frame.invert(Rect {
            x: 0,
            y: 0,
            width: 3,
            height: 2,
        });
        assert_eq!(ink_count(&frame), 5);
        assert!(!frame.has_ink(1, 1));
    }

    #[test]
    fn invert_clips_at_the_panel_edge() {
        let mut frame = Framebuffer::default();
        frame.invert(Rect {
            x: WIDTH - 1,
            y: HEIGHT - 1,
            width: 10,
            height: 10,
        });
        assert_eq!(ink_count(&frame), 1);
    }

    #[test]
    fn text_draws_glyph_columns_top_down() {
        let mut frame = Framebuffer::default();
        frame.text(0, 0, "L");
        let left_column: Vec<bool> = (0..8).map(|y| frame.has_ink(0, y)).collect();
        assert_eq!(left_column, [true, true, true, true, true, true, true, false]);
        assert!(frame.has_ink(4, 6) && !frame.has_ink(4, 5));
    }

    #[test]
    fn bar_rises_from_its_bottom_row() {
        let mut frame = Framebuffer::default();
        frame.bar(3, 8, 3);
        assert!(frame.has_ink(3, 8) && frame.has_ink(3, 6) && !frame.has_ink(3, 5));
    }
}
