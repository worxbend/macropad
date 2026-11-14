//! Puts `memory.x` where the linker looks for it, and adds defmt's linker script for a probe build.

use std::path::PathBuf;
use std::{env, fs};

fn main() {
    let out_dir = PathBuf::from(env::var_os("OUT_DIR").expect("cargo sets OUT_DIR for build scripts"));
    fs::copy("memory.x", out_dir.join("memory.x")).expect("memory.x is next to build.rs");
    println!("cargo:rustc-link-search={}", out_dir.display());
    println!("cargo:rerun-if-changed=memory.x");
    // defmt's linker script, only for a build with the `probe` feature.
    if env::var_os("CARGO_FEATURE_PROBE").is_some() {
        println!("cargo:rustc-link-arg-bins=-Tdefmt.x");
    }
}
