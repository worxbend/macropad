# Firmware tasks. Run from this directory.
ELF := target/thumbv8m.main-none-eabihf/release/macropad
UF2 := dist/macropad.uf2
UI_IMAGES := ../docs/images/ui

.PHONY: all test lint build uf2 ui-images check-pins

all: test lint uf2

test:
	cargo test

lint: check-pins
	cargo fmt --all --check
	cargo clippy --all-targets -- -D warnings
	cd fw && cargo clippy -- -D warnings

check-pins:
	python3 ../tools/check_pins.py

build:
	cd fw && cargo build --release

uf2: build
	mkdir -p dist
	cargo run --quiet -p macropad-uf2 -- $(ELF) $(UF2)

ui-images:
	cargo run --quiet -p macropad-sim -- $(UI_IMAGES)
