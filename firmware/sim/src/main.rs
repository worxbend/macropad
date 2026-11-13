//! Renders what the firmware shows, on a PC, by running the real pad logic with scripted inputs.
//!
//! `macropad-sim <picture directory> <frame directory>`
//!
//! Pictures of every screen go to the picture directory. The frames of the demo film go to the
//! frame directory as numbered PNG files; `make ui-images` joins them into `demo.gif`.

mod board;
mod canvas;
mod desk;
mod host_text;
mod panel;
mod scenes;
mod session;
mod timeline;

use std::error::Error;
use std::path::Path;
use std::{env, fs, process};

use macropad_core::framebuffer::{HEIGHT, WIDTH};
use macropad_core::ui::Screen;

use crate::canvas::{pad_picture, Canvas, BACKDROP, CAPTION};
use crate::scenes::Still;
use crate::session::{Film, Shot};

const STILL_SCALE: usize = 4;
const SHEET_SCALE: usize = 2;
const SHEET_COLUMNS: usize = 2;
const SHEET_GAP: usize = 16;
const CAPTION_HEIGHT: usize = 14;
fn still_picture(shot: &Shot) -> Canvas {
    let mut canvas = Canvas::new(WIDTH * STILL_SCALE, HEIGHT * STILL_SCALE, BACKDROP);
    canvas.display(0, 0, &shot.display, STILL_SCALE);
    canvas
}

/// Every still side by side with its caption, as the pad would look with its LEDs.
fn contact_sheet(stills: &[Still]) -> Canvas {
    let pictures: Vec<Canvas> = stills
        .iter()
        .map(|still| pad_picture(&still.shot.display, &still.shot.leds, SHEET_SCALE))
        .collect();
    let (cell_width, cell_height) = (
        pictures[0].width + SHEET_GAP,
        pictures[0].height + CAPTION_HEIGHT + SHEET_GAP,
    );
    let rows = stills.len().div_ceil(SHEET_COLUMNS);
    let mut sheet = Canvas::new(
        SHEET_COLUMNS * cell_width + SHEET_GAP,
        rows * cell_height + SHEET_GAP,
        BACKDROP,
    );
    for (index, (still, picture)) in stills.iter().zip(&pictures).enumerate() {
        let x = SHEET_GAP + index % SHEET_COLUMNS * cell_width;
        let y = SHEET_GAP + index / SHEET_COLUMNS * cell_height;
        sheet.text(x, y, still.caption, 1, CAPTION);
        sheet.paste(x, y + CAPTION_HEIGHT, picture);
    }
    sheet
}

/// The demo frame the README shows as a still: the first with two keys down on the main screen.
fn poster_frame(film: &Film) -> Option<&Shot> {
    film.frames
        .iter()
        .find(|frame| frame.screen == Screen::Main && frame.inputs.keys.count_ones() == 2)
}

/// How many demo frames show each screen, for example "splash 32, main 250".
fn screen_counts(frames: &[Shot]) -> String {
    let counts = [
        Screen::Splash,
        Screen::Main,
        Screen::System,
        Screen::Idle,
        Screen::Flash,
    ]
    .map(|screen| {
        let shown = frames.iter().filter(|frame| frame.screen == screen).count();
        format!("{} {shown}", format!("{screen:?}").to_lowercase())
    });
    counts.join(", ")
}

fn render(picture_directory: &Path, frame_directory: &Path) -> Result<(), Box<dyn Error>> {
    fs::create_dir_all(picture_directory)?;
    fs::create_dir_all(frame_directory)?;
    let stills = scenes::stills();
    for still in &stills {
        still_picture(&still.shot).write_png(&picture_directory.join(still.file_name))?;
    }
    contact_sheet(&stills).write_png(&picture_directory.join("screens.png"))?;
    let film = scenes::demo();
    let frames = &film.frames;
    for (number, frame) in frames.iter().enumerate() {
        let path = frame_directory.join(format!("demo_{number:04}.png"));
        desk::dashboard(frame, &film.host_log[..frame.log_len]).write_png(&path)?;
    }
    let poster = poster_frame(&film).ok_or("the demo has no frame with two keys down")?;
    desk::dashboard(poster, &film.host_log[..poster.log_len]).write_png(&picture_directory.join("pad.png"))?;
    timeline::led_timeline(frames).write_png(&picture_directory.join("led_timeline.png"))?;
    println!(
        "{}: {} stills, screens.png, pad.png, led_timeline.png",
        picture_directory.display(),
        stills.len()
    );
    println!(
        "{}: {} demo frames ({})",
        frame_directory.display(),
        frames.len(),
        screen_counts(frames)
    );
    Ok(())
}

fn main() {
    let arguments: Vec<String> = env::args().skip(1).collect();
    let [picture_directory, frame_directory] = arguments.as_slice() else {
        eprintln!("usage: macropad-sim <picture directory> <frame directory>");
        process::exit(2);
    };
    if let Err(error) = render(Path::new(picture_directory), Path::new(frame_directory)) {
        eprintln!("macropad-sim: {error}");
        process::exit(1);
    }
}
