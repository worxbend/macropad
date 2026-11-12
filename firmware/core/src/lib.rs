//! Hardware-independent logic of the macropad. Everything here runs and is tested on a PC.
#![cfg_attr(not(test), no_std)]

pub mod debounce;
pub mod engine;
pub mod font;
pub mod framebuffer;
pub mod hid;
pub mod keymap;
pub mod kps;
pub mod led;
pub mod quadrature;
pub mod sharp_lcd;
pub mod ui;
