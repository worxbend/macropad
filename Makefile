# Top-level tasks. `make help` lists them.
KICAD := pcb/kicad.sh
BOARD := pcb/kicad/macropad.kicad_pcb
BUILD := pcb/.build
FAB := pcb/fab
FREEROUTING_VERSION := 2.5.0
FREEROUTING_JAR := $(BUILD)/freerouting.jar
# Pinned so a changed download fails the build instead of running.
FREEROUTING_SHA256 := f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7
GERBER_LAYERS := F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts

.PHONY: help pcb pcb-place pcb-route pcb-check pcb-fab cad firmware test

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

pcb: pcb-place pcb-route pcb-check pcb-fab ## Regenerate the routed board, check it, write the fab files

pcb-place: ## board.toml + pcb/gen/circuit.py -> placed, unrouted board
	$(KICAD) python3 pcb/gen/build.py place

$(FREEROUTING_JAR):
	mkdir -p $(BUILD)
	curl -fL -o $@ https://github.com/freerouting/freerouting/releases/download/v$(FREEROUTING_VERSION)/freerouting-$(FREEROUTING_VERSION).jar
	echo "$(FREEROUTING_SHA256)  $@" | sha256sum -c -

pcb-route: $(FREEROUTING_JAR) ## Autoroute (Freerouting in a Java container), then pour ground
	docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp -v "$(CURDIR)/$(BUILD):/work" -w /work \
		eclipse-temurin:25-jre java -jar freerouting.jar -de macropad.dsn -do macropad.ses -mp 60 --gui.enabled=false
	$(KICAD) python3 pcb/gen/build.py finish

pcb-check: ## Design-rule check; fails on any error or unrouted net
	$(KICAD) kicad-cli pcb drc --severity-error --exit-code-violations --format report -o $(BUILD)/drc.rpt $(BOARD)

pcb-fab: ## Gerbers, drill files, JLCPCB BOM and placement list -> pcb/fab/
	mkdir -p $(FAB)/gerbers
	$(KICAD) kicad-cli pcb export gerbers --layers $(GERBER_LAYERS) --subtract-soldermask -o $(FAB)/gerbers/ $(BOARD)
	$(KICAD) kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-separate-th -o $(FAB)/gerbers/ $(BOARD)
	cd $(FAB) && zip -q -r -FS macropad-gerbers.zip gerbers
	$(KICAD) python3 pcb/gen/build.py fab

cad: ## Case: interference checks, then STEP/STL exports
	cd cad && .venv/bin/python build.py all

firmware: ## Tests, lints, pin check, UF2 -> firmware/dist/macropad.uf2
	$(MAKE) -C firmware all

test: ## Everything that can be checked without hardware
	python3 pcb/gen/circuit.py > /dev/null
	$(MAKE) -C firmware test check-pins
	cd cad && .venv/bin/python build.py check
