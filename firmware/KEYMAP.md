# Editing the keymap

The whole keymap is one file: [`core/src/keymap.rs`](core/src/keymap.rs). Change it, run `make`
in `firmware/`, copy `dist/macropad.uf2` to the pad.

Not tried on hardware yet. The tests and the simulator run your keymap on a PC, so a typo shows
up before you flash.

## 1. Where things are

Keys are listed row by row as you look at the pad from the front:

```
 (left knob)   [ display ]   (right knob)

   0    1    2    3
   4    5    6    7
   8    9   10   11
```

A layer is one `Layer` value:

```rust
const MEDIA: Layer = Layer {
    name: "MEDIA",                      // shown on the display, 6 characters at most
    color: Rgb::new(120, 40, 255),      // side LED colour
    effect: Effect::Breathing,          // Solid, Breathing, Rainbow or Wave
    keys: [ /* 12 bindings, in the order above */ ],
    left_knob: VOLUME,                  // what a turn sends
    right_knob: knob("BRIGHT", /* counter-clockwise */, /* clockwise */),
    right_knob_press: media("MUTE", consumer::MUTE),
};
```

The left knob's press is not bindable: a tap is "next layer", a hold opens the system functions.

## 2. Bindings

Each helper takes the label first. Labels are drawn in capitals; 6 characters fit.

| Helper | Sends | Example |
| --- | --- | --- |
| `tap(label, key)` | One key, held as long as you hold the pad's key. | `tap("F13", key::F13)` |
| `ctrl(label, key)` | Ctrl + key. | `ctrl("COPY", key::C)` |
| `chord(label, modifiers, key)` | Any modifiers + key. | `chord("REOPEN", modifier::CTRL \| modifier::SHIFT, key::T)` |
| `media(label, usage)` | A media or system key. | `media("PLAY", consumer::PLAY_PAUSE)` |
| `sequence(label, &STROKES)` | Several strokes typed one after another on one press. | `sequence("LINE", &SELECT_LINE)` |
| `tap_hold(label, tap, hold)` | `tap` when let go within 0.2 s, `hold` while kept down. | `tap_hold("TAB/SH", Stroke::plain(key::TAB), Stroke::modifiers(modifier::SHIFT))` |

Modifiers are `modifier::CTRL`, `SHIFT`, `ALT` and `GUI` (the Windows, Command or Super key).
Combine them with `|`.

Key codes are in [`core/src/hid.rs`](core/src/hid.rs): letters `key::A` to `key::Z`, digits
`key::N0` to `key::N9`, `key::F1` to `key::F24`, arrows, editing keys, punctuation and the keypad
operators. Media codes are in the `consumer` module of the same file. Codes name a key position
on a US layout: on a German layout `key::Z` types `y`.

## 3. Knobs

```rust
right_knob: knob(
    "ZOOM",                                                   // shown on the display
    Action::Stroke(Stroke::with(modifier::CTRL, key::MINUS)), // one click counter-clockwise
    Action::Stroke(Stroke::with(modifier::CTRL, key::EQUAL)), // one click clockwise
),
```

Each click sends one short tap. A knob cannot carry a `sequence`; a test rejects it.

## 4. Worked example: a browser layer in place of NUM

```rust
const BROWSER: Layer = {
    let (zoom_out, zoom_in) = strokes(
        Stroke::with(modifier::CTRL, key::MINUS),
        Stroke::with(modifier::CTRL, key::EQUAL),
    );
    let (previous_tab, next_tab) = strokes(PREVIOUS_TAB, NEXT_TAB);
    Layer {
        name: "WEB",
        color: Rgb::new(255, 60, 20),
        effect: Effect::Wave,
        keys: [
            media("BACK", consumer::BROWSER_BACK),
            media("FWD", consumer::BROWSER_FORWARD),
            media("RELOAD", consumer::BROWSER_REFRESH),
            media("HOME", consumer::BROWSER_HOME),
            ctrl("NEWTAB", key::T),
            ctrl("CLOSE", key::W),
            chord("REOPEN", modifier::CTRL | modifier::SHIFT, key::T),
            ctrl("FIND", key::F),
            ctrl("ADDR", key::L),
            ctrl("BKMARK", key::D),
            ctrl("HIST", key::H),
            tap("FULL", key::F11),
        ],
        left_knob: knob("TABS", previous_tab, next_tab),
        right_knob: knob("ZOOM", zoom_out, zoom_in),
        right_knob_press: chord("100%", modifier::CTRL, key::N0),
    }
};

pub static LAYERS: [Layer; LAYER_COUNT] = [MEDIA, EDIT, NAV, BROWSER];
```

To add a fifth layer instead, also raise `LAYER_COUNT`. The left-knob layer jump uses the four
keys of the top row, so it reaches the first four layers; tapping the left knob reaches all.

## 5. A sequence (macro)

```rust
/// Home, then Shift+End: selects the current line.
const SELECT_LINE: [Stroke; 2] = [Stroke::plain(key::HOME), Stroke::with(modifier::SHIFT, key::END)];
```

Each stroke is held for 8 ms and followed by an 8 ms pause. At most 16 strokes fit; a longer one
fails a test. The same key twice in a row works, because of the pause.

## 6. Tap-hold

```rust
// TAB when tapped. Shift while held: hold it and turn the CURSOR knob to select text.
tap_hold("TAB/SH", Stroke::plain(key::TAB), Stroke::modifiers(modifier::SHIFT)),
// ESC when tapped, Ctrl+Shift+ESC (task manager) when held.
tap_hold("ESC/TM", Stroke::plain(key::ESCAPE), Stroke::with(modifier::CTRL | modifier::SHIFT, key::ESCAPE)),
```

- The tap is sent when you let go, not when you press. Every other kind of key sends at once.
- Kept down for 0.2 s it becomes the hold. Pressing another key or turning a knob meanwhile
  makes it the hold at once, so Shift is there for that key or click.
- Keys only. A knob turn or the right knob's press cannot be tap-hold; a test rejects it.

## 7. Keys held together

- Plain keys add up: `7` and `8` held together are both down, up to six keys.
- A key with modifiers (`ctrl`, `chord`) is let go as soon as another key, a knob click or a
  sequence arrives. Otherwise UNDO held plus ESC would reach the host as Ctrl+ESC.
- A modifiers-only hold (`Stroke::modifiers(...)`) stays and applies to what follows, like
  Shift on a keyboard.
- One media key at a time. A newer one, or a media knob click, lets the held one go.

## 8. Check your work

```sh
make test        # in firmware/: fails on a label, name, macro or code the pad cannot show or send
make ui-images   # redraws ../docs/images/ui/ with your keymap, so you can read the legends
make             # everything, and the UF2
```

What the keymap tests catch:

| Mistake | Test |
| --- | --- |
| A label or layer name longer than 6 characters | `every_label_fits_its_display_cell`, `every_layer_name_fits_its_tab_and_is_unique` |
| A character the font lacks (lowercase, `~`, non-ASCII) | `every_label_and_name_uses_characters_the_font_has` |
| A sequence longer than the tap queue | `every_macro_fits_the_tap_queue` |
| A media code above `0x03FF` | `every_consumer_usage_fits_the_report_descriptor` |
| A stroke with no key, or a sequence on a knob | `no_stroke_is_empty_and_knobs_never_carry_macros` |
| A black layer colour | `every_layer_has_a_colour_the_leds_can_show` |
| Tap-hold on a knob, or with an empty half | `tap_hold_is_on_keys_only_and_both_halves_send_something` |

The simulator tests assume the stock layer order in a few places (they look for the layer named
`EDIT` after one tap). If you rename layers and a `sim` or `core` test fails on a name, that test
is telling you about its own fixture, not about your keymap; update the name it expects.
