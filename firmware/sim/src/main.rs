//! Renders the firmware's display UI for a few scenes to PNG files.
//!
//! `macropad-sim <output directory>`

use std::error::Error;
use std::fs::{self, File};
use std::io::BufWriter;
use std::path::Path;
use std::{env, process};

use macropad_core::framebuffer::{Framebuffer, HEIGHT, WIDTH};
use macropad_core::keymap::LAYERS;
use macropad_core::kps::HISTORY_BUCKETS;
use macropad_core::ui::{self, UiState};

const SCALE: usize = 4;
/// Colours of a reflective memory LCD in daylight.
const PAPER_RGB: [u8; 3] = [0xC8, 0xD0, 0xC0];
const INK_RGB: [u8; 3] = [0x1C, 0x20, 0x1A];

struct Scene {
    file_name: &'static str,
    state: UiState<'static>,
}

fn scenes() -> [Scene; 4] {
    let idle = |layer: usize| UiState {
        layer: &LAYERS[layer],
        pressed_keys: 0,
        kps_history: [0; HISTORY_BUCKETS],
        caps_lock: false,
        num_lock: false,
    };
    let typing_burst: [u8; HISTORY_BUCKETS] = core::array::from_fn(|bucket| ((bucket * 7) % 9) as u8);
    [
        Scene {
            file_name: "media.png",
            state: idle(0),
        },
        Scene {
            file_name: "edit_typing.png",
            state: UiState {
                pressed_keys: 1 << 3 | 1 << 6,
                kps_history: typing_burst,
                caps_lock: true,
                ..idle(1)
            },
        },
        Scene {
            file_name: "nav.png",
            state: UiState {
                pressed_keys: 1 << 1,
                ..idle(2)
            },
        },
        Scene {
            file_name: "num.png",
            state: UiState {
                num_lock: true,
                ..idle(3)
            },
        },
    ]
}

/// The frame as RGB bytes, each display pixel drawn as a `SCALE` x `SCALE` square.
fn scaled_rgb(frame: &Framebuffer) -> Vec<u8> {
    let mut rgb = Vec::with_capacity(WIDTH * HEIGHT * SCALE * SCALE * 3);
    for y in 0..HEIGHT * SCALE {
        for x in 0..WIDTH * SCALE {
            let color = if frame.has_ink(x / SCALE, y / SCALE) {
                INK_RGB
            } else {
                PAPER_RGB
            };
            rgb.extend_from_slice(&color);
        }
    }
    rgb
}

fn write_png(path: &Path, frame: &Framebuffer) -> Result<(), Box<dyn Error>> {
    let file = BufWriter::new(File::create(path)?);
    let mut encoder = png::Encoder::new(file, (WIDTH * SCALE) as u32, (HEIGHT * SCALE) as u32);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    encoder.write_header()?.write_image_data(&scaled_rgb(frame))?;
    Ok(())
}

fn render_scenes(output_directory: &Path) -> Result<(), Box<dyn Error>> {
    fs::create_dir_all(output_directory)?;
    for scene in scenes() {
        let path = output_directory.join(scene.file_name);
        write_png(&path, &ui::draw(&scene.state)).map_err(|error| format!("{}: {error}", path.display()))?;
        println!("{}", path.display());
    }
    Ok(())
}

fn main() {
    let Some(output_directory) = env::args().nth(1) else {
        eprintln!("usage: macropad-sim <output directory>");
        process::exit(2);
    };
    if let Err(error) = render_scenes(Path::new(&output_directory)) {
        eprintln!("macropad-sim: {error}");
        process::exit(1);
    }
}
