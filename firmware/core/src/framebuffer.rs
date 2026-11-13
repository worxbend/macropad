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

impl Rect {
    /// The rectangle `margin` pixels smaller on every side. It must be big enough for that.
    pub const fn inset(self, margin: usize) -> Self {
        Self {
            x: self.x + margin,
            y: self.y + margin,
            width: self.width - 2 * margin,
            height: self.height - 2 * margin,
        }
    }

    fn pixels(self) -> impl Iterator<Item = (usize, usize)> {
        let xs = self.x..(self.x + self.width).min(WIDTH);
        (self.y..(self.y + self.height).min(HEIGHT)).flat_map(move |y| xs.clone().map(move |x| (x, y)))
    }
}

/// A small picture: one byte per row, top first; bit 7 is the leftmost pixel.
pub type Sprite<const ROWS: usize> = [u8; ROWS];

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
        area.pixels().for_each(|(x, y)| self.rows[y][x / 8] ^= pixel_mask(x));
    }

    /// Darkens every pixel of the area.
    pub fn fill(&mut self, area: Rect) {
        area.pixels().for_each(|(x, y)| self.rows[y][x / 8] |= pixel_mask(x));
    }

    /// Wipes the area back to paper.
    pub fn clear(&mut self, area: Rect) {
        area.pixels().for_each(|(x, y)| self.rows[y][x / 8] &= !pixel_mask(x));
    }

    /// Draws the one-pixel border of the area. Its inside is left alone.
    pub fn outline(&mut self, area: Rect) {
        if area.width == 0 || area.height == 0 {
            return;
        }
        let (right, bottom) = (area.x + area.width - 1, area.y + area.height - 1);
        for x in area.x..=right {
            self.ink(x, area.y);
            self.ink(x, bottom);
        }
        for y in area.y..=bottom {
            self.ink(area.x, y);
            self.ink(right, y);
        }
    }

    pub fn sprite<const ROWS: usize>(&mut self, x: usize, y: usize, sprite: &Sprite<ROWS>) {
        for (row, bits) in sprite.iter().enumerate() {
            for column in (0..8).filter(|column| bits & (0x80 >> column) != 0) {
                self.ink(x + column, y + row);
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

    /// Draws text with every font pixel enlarged to a `scale` x `scale` square.
    pub fn big_text(&mut self, x: usize, y: usize, text: &str, scale: usize) {
        for (index, character) in text.chars().enumerate() {
            let glyph_x = x + index * ADVANCE * scale;
            for (column, bits) in glyph(character).into_iter().enumerate() {
                for row in (0..GLYPH_HEIGHT).filter(|row| bits & (1 << row) != 0) {
                    self.fill(Rect {
                        x: glyph_x + column * scale,
                        y: y + row * scale,
                        width: scale,
                        height: scale,
                    });
                }
            }
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

    #[test]
    fn fill_then_clear_leaves_only_the_frame_between_them() {
        let mut frame = Framebuffer::default();
        let area = Rect {
            x: 10,
            y: 10,
            width: 6,
            height: 4,
        };
        frame.fill(area);
        assert_eq!(ink_count(&frame), 24);
        frame.clear(area.inset(1));
        assert_eq!(ink_count(&frame), 24 - 4 * 2);
        assert!(frame.has_ink(10, 10) && !frame.has_ink(11, 11));
    }

    #[test]
    fn outline_draws_the_border_only_and_clips() {
        let mut frame = Framebuffer::default();
        frame.outline(Rect {
            x: 2,
            y: 2,
            width: 5,
            height: 4,
        });
        assert_eq!(ink_count(&frame), 2 * 5 + 2 * 2);
        assert!(!frame.has_ink(3, 3));
        frame.outline(Rect {
            x: WIDTH - 2,
            y: HEIGHT - 2,
            width: 9,
            height: 9,
        });
        assert!(frame.has_ink(WIDTH - 1, HEIGHT - 2));
    }

    #[test]
    fn an_empty_outline_draws_nothing() {
        let mut frame = Framebuffer::default();
        frame.outline(Rect {
            x: 5,
            y: 5,
            width: 0,
            height: 3,
        });
        assert_eq!(ink_count(&frame), 0);
    }

    #[test]
    fn sprite_rows_run_left_to_right_from_bit_seven() {
        let mut frame = Framebuffer::default();
        frame.sprite(4, 1, &[0b1010_0000, 0b0000_0001]);
        assert!(frame.has_ink(4, 1) && !frame.has_ink(5, 1) && frame.has_ink(6, 1));
        assert!(frame.has_ink(11, 2));
        assert_eq!(ink_count(&frame), 3);
    }

    #[test]
    fn big_text_is_the_small_text_with_every_pixel_enlarged() {
        let (mut small, mut big) = (Framebuffer::default(), Framebuffer::default());
        small.text(0, 0, "R2");
        big.big_text(0, 0, "R2", 3);
        assert_eq!(ink_count(&big), 9 * ink_count(&small));
        for (x, y) in [(0, 0), (4, 6), (7, 3), (10, 0)] {
            assert_eq!(big.has_ink(3 * x + 1, 3 * y + 2), small.has_ink(x, y), "({x}, {y})");
        }
    }
}
