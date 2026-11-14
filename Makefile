# Top-level tasks. `make help` lists them.
KICAD := pcb/kicad.sh
BOARD := pcb/kicad/macropad.kicad_pcb
BUILD := pcb/.build
FAB := pcb/fab
GERBER_LAYERS := F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts

.PHONY: help pcb pcb-place pcb-check pcb-fab pcb-test cad firmware ui-images docs-check site site-serve site-shots test

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

pcb: pcb-place pcb-check pcb-fab ## Regenerate the routed board, check it, write the order files (needs Docker)

pcb-place: ## board.toml + pcb/gen/circuit.py -> schematic, placed and routed board, 3D models, pictures
	$(KICAD) python3 pcb/gen/build.py place

pcb-check: ## Design-rule check against the schematic; fails on any error or unconnected item
	mkdir -p $(BUILD)
	$(KICAD) kicad-cli pcb drc --severity-error --schematic-parity --exit-code-violations --format report -o $(BUILD)/drc.rpt $(BOARD)

pcb-fab: ## Gerbers, drill files, JLCPCB and PCBWay BOMs, placement list -> pcb/fab/, then a check that they agree
	mkdir -p $(FAB)/gerbers
	$(KICAD) kicad-cli pcb export gerbers --layers $(GERBER_LAYERS) --subtract-soldermask -o $(FAB)/gerbers/ $(BOARD)
	$(KICAD) kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-separate-th -o $(FAB)/gerbers/ $(BOARD)
	cd $(FAB) && zip -q -r -FS macropad-gerbers.zip gerbers
	$(KICAD) python3 pcb/gen/build.py fab

pcb-test: ## Netlist self-check, router and schematic-writer unit tests (no Docker)
	python3 pcb/gen/circuit.py > /dev/null
	python3 -m unittest discover -s pcb/gen -p 'test_*.py'

cad: ## Case: self-test, checks, STEP/STL exports, renders, drawings (needs cad/.venv, about 3 minutes)
	cd cad && .venv/bin/python build.py all

firmware: ## Tests, lints, board and HID checks, UF2 -> firmware/dist/macropad.uf2
	$(MAKE) -C firmware all

ui-images: ## Simulator: redraw docs/images/ui/ and the demo GIF (needs ImageMagick, about 1 minute)
	$(MAKE) -C firmware ui-images

docs-check: ## Every file and picture named in a Markdown file exists
	python3 .github/scripts/check_docs.py

SITE_PYTHON ?= python3
SITE_PORT ?= 8000
SHOTS ?= .build/site-shots

site: ## Microsite: site/ plus the pictures it names from docs/images/ -> _site/, with its checks (published by GitHub Pages)
	$(SITE_PYTHON) .github/scripts/build_site.py

site-serve: ## Microsite: build, serve on 127.0.0.1:$(SITE_PORT) and rebuild on every change (Ctrl+C stops)
	$(SITE_PYTHON) .github/scripts/build_site.py --serve $(SITE_PORT)

site-shots: site ## Microsite: headless Firefox screenshots of pages and scroll scenes -> $(SHOTS)/
	site/shots.sh $(SHOTS)

test: pcb-test docs-check site ## Everything that can be checked without Docker or hardware
	$(MAKE) -C firmware test check-pins check-hid
	cd cad && .venv/bin/python build.py check
