//! `macropad-uf2 <firmware.elf> <firmware.uf2>`

use std::error::Error;
use std::{env, fs, process};

fn main() {
    let arguments: Vec<String> = env::args().skip(1).collect();
    let [elf_path, uf2_path] = arguments.as_slice() else {
        eprintln!("usage: macropad-uf2 <firmware.elf> <firmware.uf2>");
        process::exit(2);
    };
    if let Err(error) = convert(elf_path, uf2_path) {
        eprintln!("macropad-uf2: {error}");
        process::exit(1);
    }
}

fn convert(elf_path: &str, uf2_path: &str) -> Result<(), Box<dyn Error>> {
    let elf = fs::read(elf_path).map_err(|error| format!("{elf_path}: {error}"))?;
    let uf2 = macropad_uf2::elf_to_uf2(&elf).map_err(|error| format!("{elf_path}: {error}"))?;
    fs::write(uf2_path, &uf2).map_err(|error| format!("{uf2_path}: {error}"))?;
    println!(
        "{uf2_path}: {} blocks, {} bytes of flash",
        uf2.len() / 512,
        uf2.len() / 2
    );
    Ok(())
}
