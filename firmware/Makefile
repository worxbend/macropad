# Firmware tasks. Run from this directory.
ELF := target/thumbv8m.main-none-eabihf/release/macropad
UF2 := dist/macropad.uf2
UI_IMAGES := ../docs/images/ui
UI_FRAMES := target/ui-frames
# The demo film is recorded at 20 frames per second; GIF delays count in 1/100 s.
GIF_FRAME_DELAY := 5

.PHONY: all test lint build uf2 probe ui-images check-pins check-hid

all: test lint uf2

test:
	cargo test

lint: check-pins check-hid
	cargo fmt --all --check
	cargo clippy --all-targets -- -D warnings
	cd fw && cargo clippy -- -D warnings
	cd fw && cargo clippy --features probe -- -D warnings

check-pins:
	python3 ../tools/check_pins.py

check-hid:
	python3 ../tools/check_hid.py

build:
	cd fw && cargo build --release

uf2: build
	mkdir -p dist
	cargo run --quiet -p macropad-uf2 -- $(ELF) $(UF2)

# Firmware that logs over a debug probe (defmt over RTT). It is written to the same ELF path as
# `build`, so `uf2` rebuilds without the feature first. Flash and watch the log with
# `cd fw && cargo run --release --features probe` (needs probe-rs).
probe:
	cd fw && cargo build --release --features probe

# Needs ImageMagick (`magick`) to join the demo frames into a GIF. These two optimisations keep
# every pixel's colour; plain `-layers Optimize` merged the backdrop into the display's ink colour.
ui-images:
	rm -rf $(UI_FRAMES)
	cargo run --quiet --release -p macropad-sim -- $(UI_IMAGES) $(UI_FRAMES)
	magick -delay $(GIF_FRAME_DELAY) -loop 0 $(UI_FRAMES)/demo_*.png -dither None \
		-layers OptimizeFrame -layers OptimizeTransparency $(UI_IMAGES)/demo.gif
