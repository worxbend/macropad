//! An RGB picture that can show the pad: the display, and the light of the side LEDs.

use std::error::Error;
use std::fs::File;
use std::io::BufWriter;
use std::path::Path;

use macropad_core::font::{glyph, ADVANCE, GLYPH_HEIGHT};
use macropad_core::framebuffer::{Framebuffer, HEIGHT, WIDTH};
use macropad_core::led::{LedFrame, Rgb, LED_COUNT};

pub type Color = [u8; 3];

/// Colours of a reflective memory LCD in daylight.
pub const PAPER: Color = [0xC8, 0xD0, 0xC0];
pub const INK: Color = [0x1C, 0x20, 0x1A];
pub const BACKDROP: Color = [0x14, 0x16, 0x1A];
pub const CAPTION: Color = [0xD8, 0xDC, 0xE2];
const BEZEL: Color = [0x2A, 0x2D, 0x33];

/// Sizes of the pad picture in display pixels; multiply by the scale for picture pixels.
const OUTER_MARGIN: usize = 3;
const STRIP_WIDTH: usize = 5;
const STRIP_GAP: usize = 3;
const BEZEL_WIDTH: usize = 4;
const LEDS_PER_SIDE: usize = LED_COUNT / 2;

pub struct Canvas {
    pub width: usize,
    pub height: usize,
    rgb: Vec<u8>,
}

impl Canvas {
    pub fn new(width: usize, height: usize, color: Color) -> Self {
        Self {
            width,
            height,
            rgb: color.repeat(width * height),
        }
    }

    pub fn pixel(&self, x: usize, y: usize) -> Color {
        let start = (y * self.width + x) * 3;
        [self.rgb[start], self.rgb[start + 1], self.rgb[start + 2]]
    }

    /// Paints a rectangle. Parts outside the canvas are clipped.
    pub fn fill(&mut self, x: usize, y: usize, width: usize, height: usize, color: Color) {
        for row in y..(y + height).min(self.height) {
            for column in x..(x + width).min(self.width) {
                let start = (row * self.width + column) * 3;
                self.rgb[start..start + 3].copy_from_slice(&color);
            }
        }
    }

    /// Paints every pixel of the box around (`centre_x`, `centre_y`) for which `covers` says yes.
    /// `covers` gets the offset from the centre. Parts outside the canvas are clipped.
    fn shape(&mut self, centre: (i32, i32), half: (i32, i32), color: Color, covers: impl Fn(i32, i32) -> bool) {
        for dy in -half.1..=half.1 {
            for dx in -half.0..=half.0 {
                let (x, y) = (centre.0 + dx, centre.1 + dy);
                if x >= 0 && y >= 0 && covers(dx, dy) {
                    self.fill(x as usize, y as usize, 1, 1, color);
                }
            }
        }
    }

    pub fn disc(&mut self, centre: (i32, i32), radius: i32, color: Color) {
        self.shape(centre, (radius, radius), color, |dx, dy| {
            dx * dx + dy * dy <= radius * radius
        });
    }

    /// A box of `2 * half + 1` pixels each way whose corners are quarter circles.
    pub fn rounded(&mut self, centre: (i32, i32), half: (i32, i32), corner_radius: i32, color: Color) {
        let straight = (half.0 - corner_radius, half.1 - corner_radius);
        self.shape(centre, half, color, |dx, dy| {
            let (past_x, past_y) = ((dx.abs() - straight.0).max(0), (dy.abs() - straight.1).max(0));
            past_x * past_x + past_y * past_y <= corner_radius * corner_radius
        });
    }

    /// Adds light to one pixel, as a glow does. Pixels outside the canvas are ignored.
    pub fn add_light(&mut self, x: i32, y: i32, light: Color, share: f32) {
        if x < 0 || y < 0 || x as usize >= self.width || y as usize >= self.height {
            return;
        }
        let start = (y as usize * self.width + x as usize) * 3;
        for (channel, added) in self.rgb[start..start + 3].iter_mut().zip(light) {
            *channel = channel.saturating_add((f32::from(added) * share) as u8);
        }
    }

    /// Draws text in the firmware's own font, each font pixel `scale` picture pixels wide.
    pub fn text(&mut self, x: usize, y: usize, text: &str, scale: usize, color: Color) {
        for (index, character) in text.chars().enumerate() {
            for (column, bits) in glyph(character).into_iter().enumerate() {
                for row in (0..GLYPH_HEIGHT).filter(|row| bits & (1 << row) != 0) {
                    let pixel_x = x + (index * ADVANCE + column) * scale;
                    self.fill(pixel_x, y + row * scale, scale, scale, color);
                }
            }
        }
    }

    /// Draws the display contents, each display pixel as a `scale` x `scale` square.
    pub fn display(&mut self, x: usize, y: usize, frame: &Framebuffer, scale: usize) {
        for row in 0..HEIGHT {
            for column in 0..WIDTH {
                let color = if frame.has_ink(column, row) { INK } else { PAPER };
                self.fill(x + column * scale, y + row * scale, scale, scale, color);
            }
        }
    }

    /// Copies another picture onto this one with its top-left corner at (`x`, `y`).
    pub fn paste(&mut self, x: usize, y: usize, picture: &Canvas) {
        for row in 0..picture.height {
            for column in 0..picture.width {
                self.fill(x + column, y + row, 1, 1, picture.pixel(column, row));
            }
        }
    }

    pub fn write_png(&self, path: &Path) -> Result<(), Box<dyn Error>> {
        let file = BufWriter::new(File::create(path).map_err(|error| format!("{}: {error}", path.display()))?);
        let mut encoder = png::Encoder::new(file, self.width as u32, self.height as u32);
        encoder.set_color(png::ColorType::Rgb);
        encoder.set_depth(png::BitDepth::Eight);
        encoder.write_header()?.write_image_data(&self.rgb)?;
        Ok(())
    }
}

/// The colour to paint for an LED value.
///
/// LED values are linear light and, after the current cap, numerically small. A square-root
/// curve makes them look on a monitor roughly as bright as they would to the eye.
pub fn led_on_screen(led: Rgb) -> Color {
    [led.r, led.g, led.b].map(|channel| (f32::from(channel) / 255.0).sqrt().mul_add(255.0, 0.5) as u8)
}

/// The pad seen from above: the display in its bezel, with a strip of LED light on each side.
pub fn pad_picture(frame: &Framebuffer, leds: &LedFrame, scale: usize) -> Canvas {
    let side = OUTER_MARGIN + STRIP_WIDTH + STRIP_GAP;
    let bezel_width = WIDTH + 2 * BEZEL_WIDTH;
    let bezel_height = HEIGHT + 2 * BEZEL_WIDTH;
    let mut canvas = Canvas::new(
        (2 * side + bezel_width) * scale,
        (2 * OUTER_MARGIN + bezel_height) * scale,
        BACKDROP,
    );
    let top = OUTER_MARGIN * scale;
    canvas.fill(side * scale, top, bezel_width * scale, bezel_height * scale, BEZEL);
    canvas.display((side + BEZEL_WIDTH) * scale, top + BEZEL_WIDTH * scale, frame, scale);
    // Chain order: right side back to front (top to bottom here), then left side front to back.
    let right: [Rgb; LEDS_PER_SIDE] = core::array::from_fn(|place| leds[place]);
    let left: [Rgb; LEDS_PER_SIDE] = core::array::from_fn(|place| leds[LED_COUNT - 1 - place]);
    let strip = Strip {
        y: top,
        width: STRIP_WIDTH * scale,
        height: bezel_height * scale,
    };
    strip.draw(&mut canvas, OUTER_MARGIN * scale, &left);
    strip.draw(&mut canvas, (side + bezel_width + STRIP_GAP) * scale, &right);
    canvas
}

/// A diffuser strip: the light of its LEDs, top to bottom, blended along its length.
struct Strip {
    y: usize,
    width: usize,
    height: usize,
}

impl Strip {
    fn draw(&self, canvas: &mut Canvas, x: usize, leds: &[Rgb; LEDS_PER_SIDE]) {
        for row in 0..self.height {
            let color = led_on_screen(self.light_at(row, leds));
            canvas.fill(x, self.y + row, self.width, 1, color);
        }
    }

    /// LED `n` sits at (2n + 1) / 8 of the strip; between two LEDs their light is mixed.
    fn light_at(&self, row: usize, leds: &[Rgb; LEDS_PER_SIDE]) -> Rgb {
        let spacing = self.height / LEDS_PER_SIDE;
        let from_first = row.saturating_sub(spacing / 2);
        let above = from_first / spacing;
        if above >= LEDS_PER_SIDE - 1 {
            return leds[LEDS_PER_SIDE - 1];
        }
        let toward_next = (from_first % spacing * 255 / spacing) as u8;
        leds[above].mixed(leds[above + 1], toward_next)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const RED: Rgb = Rgb::new(255, 0, 0);
    const BLUE: Rgb = Rgb::new(0, 0, 255);

    #[test]
    fn text_uses_the_firmware_font_at_the_given_scale() {
        let mut canvas = Canvas::new(20, 20, BACKDROP);
        canvas.text(1, 1, "L", 2, CAPTION);
        assert_eq!(canvas.pixel(1, 1), CAPTION);
        assert_eq!(canvas.pixel(2, 14), CAPTION);
        assert_eq!(canvas.pixel(5, 5), BACKDROP);
        assert_eq!(canvas.pixel(9, 13), CAPTION);
    }

    #[test]
    fn a_disc_is_round_and_clips_at_the_canvas_edge() {
        let mut canvas = Canvas::new(12, 12, BACKDROP);
        canvas.disc((2, 6), 4, INK);
        assert_eq!(canvas.pixel(6, 6), INK);
        assert_eq!(canvas.pixel(2, 2), INK);
        assert_eq!(canvas.pixel(5, 3), BACKDROP);
        assert_eq!(canvas.pixel(0, 6), INK);
    }

    #[test]
    fn a_rounded_box_is_filled_except_for_its_corners() {
        let mut canvas = Canvas::new(21, 21, BACKDROP);
        canvas.rounded((10, 10), (8, 6), 3, INK);
        assert_eq!(canvas.pixel(2, 10), INK);
        assert_eq!(canvas.pixel(10, 4), INK);
        assert_eq!(canvas.pixel(2, 4), BACKDROP);
        assert_eq!(canvas.pixel(3, 5), INK);
        assert_eq!(canvas.pixel(1, 10), BACKDROP);
    }

    #[test]
    fn added_light_brightens_and_saturates() {
        let mut canvas = Canvas::new(2, 1, [250, 10, 0]);
        canvas.add_light(0, 0, [100, 100, 100], 0.5);
        canvas.add_light(5, 0, [100, 100, 100], 0.5);
        assert_eq!(canvas.pixel(0, 0), [255, 60, 50]);
        assert_eq!(canvas.pixel(1, 0), [250, 10, 0]);
    }

    #[test]
    fn fill_clips_at_the_canvas_edge() {
        let mut canvas = Canvas::new(4, 4, BACKDROP);
        canvas.fill(3, 3, 10, 10, INK);
        assert_eq!(canvas.pixel(3, 3), INK);
        assert_eq!(canvas.pixel(2, 3), BACKDROP);
    }

    #[test]
    fn led_values_are_brightened_but_black_stays_black() {
        assert_eq!(led_on_screen(Rgb::BLACK), [0, 0, 0]);
        assert_eq!(led_on_screen(Rgb::WHITE), [255, 255, 255]);
        assert_eq!(led_on_screen(Rgb::new(64, 0, 0)), [128, 0, 0]);
    }

    #[test]
    fn the_right_strip_shows_the_first_four_leds_top_down_and_the_left_the_rest_bottom_up() {
        let mut leds = [Rgb::BLACK; LED_COUNT];
        leds[0] = RED;
        leds[4] = BLUE;
        let scale = 2;
        let picture = pad_picture(&Framebuffer::default(), &leds, scale);
        let strip_top = OUTER_MARGIN * scale;
        let strip_bottom = picture.height - OUTER_MARGIN * scale - 1;
        let (left_x, right_x) = (OUTER_MARGIN * scale, picture.width - OUTER_MARGIN * scale - 1);
        assert_eq!(picture.pixel(right_x, strip_top), [255, 0, 0]);
        assert_eq!(picture.pixel(right_x, strip_bottom), [0, 0, 0]);
        assert_eq!(picture.pixel(left_x, strip_bottom), [0, 0, 255]);
        assert_eq!(picture.pixel(left_x, strip_top), [0, 0, 0]);
    }

    #[test]
    fn light_between_two_leds_is_a_mix_of_both() {
        let strip = Strip {
            y: 0,
            width: 1,
            height: 80,
        };
        let leds = [RED, BLUE, BLUE, BLUE];
        assert_eq!(strip.light_at(10, &leds), RED);
        let between = strip.light_at(20, &leds);
        assert!(between.r > 0 && between.b > 0);
        assert_eq!(strip.light_at(79, &leds), BLUE);
    }
}
