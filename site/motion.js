// Motion and small widgets for the macropad page. Plain JavaScript, no dependencies.
//
// Scroll scenes: each scene maps scroll position to a progress p from 0 to 1 and writes only
// transform and opacity (plus one stroke-dashoffset, see the signature scene). Offsets are measured
// on load and on resize, never inside the frame loop, and scenes far from the viewport are skipped.
// Without html.motion (no JavaScript, reduced motion, ?motion=off) nothing here moves anything and
// the CSS shows every scene in its final, readable state.
//
// Debug parameters (read once at start):
//   ?frame=0.5                    every scene at progress 0.5, scrolling ignored
//   ?frame=light:0.3,hero:1       named scenes at the given progress
//   ?only=signature               hide every other section (the header stays)
//   ?motion=off                   the reduced-motion page (also read by the script in <head>)
//   ?debug=bands,sigbox,width,errors  outline the exploded bands and the signature target, show the
//                                 page width, print script errors on the page
"use strict";

(function () {
  const clamp01 = (v) => Math.min(1, Math.max(0, v));
  const range = (p, from, to) => clamp01((p - from) / (to - from));
  const mix = (a, b, t) => a + (b - a) * t;
  const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  const root = document.documentElement;
  const params = new URLSearchParams(location.search);
  const frames = parseFrames(params.get("frame"));
  const debug = new Set((params.get("debug") || "").split(",").filter(Boolean));
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  if (debug.has("errors")) {
    // Screenshots have no console: print script errors on the page instead.
    addEventListener("error", (event) => {
      const line = document.createElement("p");
      line.className = "debug-badge";
      line.textContent = `${event.message} (${event.lineno}:${event.colno})`;
      document.body.append(line);
    });
  }

  function parseFrames(value) {
    if (value === null) return null;
    const named = {};
    let all = null;
    for (const item of value.split(",")) {
      const [name, p] = item.includes(":") ? item.split(":") : [null, item];
      const number = clamp01(parseFloat(p));
      if (Number.isNaN(number)) continue;
      if (name) named[name] = number;
      else all = number;
    }
    return { all, named };
  }

  // ---------------------------------------------------------------- debug helpers

  function applyDebug() {
    const only = params.get("only");
    if (only) {
      for (const section of document.querySelectorAll("main > section, body > footer")) {
        section.hidden = section.id !== only;
      }
    }
    for (const flag of debug) root.classList.add("debug-" + flag);
    // Screenshots are taken at load: fetch every picture now instead of when it scrolls near.
    if (frames || only || params.has("motion")) {
      for (const img of document.querySelectorAll('img[loading="lazy"]')) img.loading = "eager";
    }
    if (debug.has("width")) {
      const badge = document.createElement("p");
      badge.className = "debug-badge";
      document.body.append(badge);
      const show = () => {
        const overflow = root.scrollWidth - root.clientWidth;
        badge.textContent = `scrollWidth ${root.scrollWidth} / clientWidth ${root.clientWidth}` + (overflow > 0 ? " OVERFLOW" : " ok");
      };
      addEventListener("load", show);
      addEventListener("resize", show);
      show();
    }
  }

  // ---------------------------------------------------------------- measuring

  // Layout position of an element inside an ancestor, from offsetLeft/offsetTop: unlike
  // getBoundingClientRect it ignores transforms, so a moving element can be measured mid-animation.
  function offsetWithin(element, ancestor) {
    let x = 0;
    let y = 0;
    let node = element;
    while (node && node !== ancestor) {
      x += node.offsetLeft;
      y += node.offsetTop;
      node = node.offsetParent;
    }
    return { x, y, w: element.offsetWidth, h: element.offsetHeight };
  }

  function pageTop(element) {
    return element.getBoundingClientRect().top + scrollY;
  }

  const headerHeight = () => document.querySelector(".top").offsetHeight;

  // ---------------------------------------------------------------- scenes

  // A track scene has a sticky stage inside a tall .track; p runs while the stage is stuck.
  // The CSS sets --scene: 1 on a stage where it is sticky at the current width.
  function trackScene(id, parts) {
    const section = document.getElementById(id);
    if (!section) return null;
    const track = section.querySelector(".track");
    const stage = section.querySelector(".stage");
    const scene = {
      id,
      section,
      observed: track,
      top: 0,
      length: 1,
      enabled: false,
      measure() {
        scene.enabled = getComputedStyle(stage).getPropertyValue("--scene").trim() === "1";
        scene.top = pageTop(track) - headerHeight();
        scene.length = Math.max(1, track.offsetHeight - stage.offsetHeight);
        if (parts.measure) parts.measure(stage);
      },
      progress(y) {
        return clamp01((y - scene.top) / scene.length);
      },
      update: parts.update,
      reset: parts.reset,
    };
    return scene;
  }

  // A view scene moves elements while they cross the viewport; each element has its own p.
  function viewScene(id, selector, from, to, apply) {
    const section = document.getElementById(id);
    if (!section) return null;
    const items = [...section.querySelectorAll(selector)].map((element) => ({ element, top: 0, height: 0 }));
    const scene = {
      id,
      section,
      observed: section,
      enabled: true,
      measure() {
        for (const item of items) {
          item.top = pageTop(item.element);
          item.height = item.element.offsetHeight;
        }
      },
      // The element's top moves from `from` to `to`, as fractions of the viewport height.
      progressOf(item, y) {
        const viewport = innerHeight;
        const topInView = item.top - y;
        return clamp01((from * viewport - topInView) / ((from - to) * viewport));
      },
      progress(y) {
        return y;
      },
      update(y, fixed) {
        for (const item of items) apply(item.element, fixed ?? scene.progressOf(item, y));
      },
      reset() {
        for (const item of items) apply(item.element, null);
      },
    };
    return scene;
  }

  function setStyle(element, transform, opacity) {
    element.style.transform = transform ?? "";
    element.style.opacity = opacity ?? "";
  }

  // ---- hero: the picture rises from below the copy and pulls back from the deck.
  function heroScene() {
    let copyHeight = 0;
    const section = document.getElementById("hero");
    const copy = section.querySelector('[data-part="copy"]');
    const image = section.querySelector('[data-part="image"]');
    image.style.transformOrigin = "50% 38%";
    return trackScene("hero", {
      measure() {
        copyHeight = copy.offsetHeight;
      },
      update(p) {
        const move = easeInOutCubic(range(p, 0, 0.75));
        const lift = mix(copyHeight * 0.92, 0, move);
        setStyle(image, `translate3d(0, ${lift}px, 0) scale(${mix(1.22, 1, move)})`);
        // The copy is gone before the product reaches it.
        const fade = range(p, 0.05, 0.35);
        setStyle(copy, `translate3d(0, ${mix(0, -8, fade)}vh, 0)`, 1 - fade);
      },
      reset() {
        setStyle(image);
        setStyle(copy);
      },
    });
  }

  // ---- manifesto: phrases light up in reading order; the last one draws its hairline.
  function wordsScene() {
    const section = document.getElementById("words");
    const paragraph = section.querySelector('[data-part="manifesto"]');
    const phrases = [...paragraph.children];
    const last = paragraph.querySelector(".manifesto-last");
    const scene = viewScene("words", '[data-part="manifesto"]', 0.85, 0.3, (element, p) => {
      phrases.forEach((phrase, index) => {
        phrase.style.opacity = p === null ? "" : 0.3 + 0.7 * clamp01((p * phrases.length) - index);
      });
      last.style.setProperty("--hairline", p === null ? 1 : clamp01((p * phrases.length) - (phrases.length - 1)));
    });
    return scene;
  }

  // ---- design: parallax on the chalk render, the seam reaching out from the side render.
  function designScene() {
    const section = document.getElementById("design");
    const seamFrame = section.querySelector(".seam-shot .frame");
    const left = section.querySelector('[data-part="seam-left"]');
    const right = section.querySelector('[data-part="seam-right"]');
    const parallax = viewScene("design", '[data-part="parallax"]', 1, -0.75, (element, p) => {
      setStyle(element, p === null ? null : `translate3d(0, ${mix(5, -5, p)}%, 0) scale(1.1)`);
    });
    const seamItem = { element: seamFrame, top: 0, height: 0 };
    return {
      ...parallax,
      measure() {
        parallax.measure();
        seamItem.top = pageTop(seamFrame);
      },
      update(y, fixed) {
        parallax.update(y, fixed);
        const p = fixed ?? clamp01((0.75 * innerHeight - (seamItem.top - y)) / (0.35 * innerHeight));
        left.style.transform = `scaleX(${p})`;
        right.style.transform = `scaleX(${p})`;
      },
      reset() {
        parallax.reset();
        setStyle(left);
        setStyle(right);
      },
    };
  }

  // ---- close-ups settle from a slight zoom as they come in.
  function settleScene(id, from, to, scaleFrom) {
    return viewScene(id, '[data-part="settle"]', from, to, (element, p) => {
      const target = element.classList.contains("clip") ? element.firstElementChild : element;
      setStyle(target, p === null ? null : `scale(${mix(scaleFrom, 1, p)})`);
    });
  }

  // ---- board: the populated board drifts inside its plate.
  function boardScene() {
    return viewScene("board", '[data-part="parallax"]', 1, -0.6, (element, p) => {
      setStyle(element, p === null ? null : `translate3d(0, ${mix(4, -4, p)}%, 0) scale(1.09)`);
    });
  }

  // ---- light: the studio goes dark, the LEDs step on, then the render's own glow takes over.
  function lightScene() {
    const section = document.getElementById("light");
    const dim = section.querySelector('[data-part="dim"]');
    const veil = section.querySelector('[data-part="veil"]');
    const leds = [...section.querySelectorAll('[data-part="led"]')];
    return trackScene("light", {
      update(p) {
        dim.style.opacity = 1 - range(p, 0, 0.1);
        veil.style.opacity = 0.94 * (1 - range(p, 0.45, 0.8));
        const fade = 1 - range(p, 0.55, 0.8);
        leds.forEach((led, index) => {
          const on = range(p, 0.12 + index * 0.08, 0.2 + index * 0.08);
          setStyle(led, `scaleX(${mix(0.6, 1, on)})`, on * fade);
        });
      },
      reset() {
        setStyle(dim);
        setStyle(veil);
        for (const led of leds) setStyle(led);
      },
    });
  }

  // ---- exploded: five bands of the render start pushed together and open to the exact picture.
  function explodedScene() {
    const section = document.getElementById("exploded");
    const bands = [...section.querySelectorAll('[data-part="band"]')];
    const labels = [...section.querySelectorAll('[data-part="label"]')];
    // Offsets at the start, in % of the image height, top group first. The outer groups start early.
    const pushed = [8.8, 5.3, 0, -4.7, -10];
    const head = [0.05, 0, 0, 0, 0.05];
    return trackScene("exploded", {
      update(p) {
        bands.forEach((band, index) => {
          const start = 0.15 - head[index];
          const t = easeInOutCubic(range(p, start, 0.75));
          band.style.transform = `translate3d(0, ${mix(pushed[index], 0, t)}%, 0)`;
          labels[index].style.opacity = 0.35 + 0.65 * range(t, 0.8, 1);
        });
      },
      reset() {
        for (const band of bands) setStyle(band);
        for (const label of labels) setStyle(label);
      },
    });
  }

  // ---- firmware: scroll scrubs through the eleven screens, one frame at a time like an LCD.
  function firmwareScene() {
    const section = document.getElementById("firmware");
    const screens = [...section.querySelectorAll('[data-part="screen"]')];
    const names = [...section.querySelectorAll('[data-part="name"]')];
    return trackScene("firmware", {
      update(p) {
        const shown = Math.min(screens.length - 1, Math.floor(p * screens.length));
        screens.forEach((screen, index) => {
          screen.style.opacity = index === shown ? 1 : 0;
          names[index].style.opacity = index === shown ? 1 : 0.45;
        });
      },
      reset() {
        for (const element of [...screens, ...names]) setStyle(element);
      },
    });
  }

  // ---- signature: the hairline arrives, the signature is drawn, then lands on its laser mark.
  // Target: the mark in underside_aluminium.png, pixels x 437-747, y 531-682 of 1600 x 1100.
  // Re-measure it if `make cad` renders the underside with another camera.
  const SIGNATURE_MARK = { x: 437 / 1600, y: 531 / 1100, w: 310 / 1600, h: 151 / 1100 };

  function signatureScene() {
    const section = document.getElementById("signature");
    const hairline = section.querySelector('[data-part="hairline"]');
    const figure = section.querySelector('[data-part="signature"]');
    const svg = figure.querySelector("svg");
    const paths = [...svg.querySelectorAll("path")];
    const render = section.querySelector('[data-part="render"]');
    const image = render.querySelector("img");
    const fadeIn = [...section.querySelectorAll('[data-part="edition"], [data-part="body"]')];
    const lengths = paths.map((path) => path.getTotalLength());
    const total = lengths.reduce((a, b) => a + b, 0);
    let landing = { dx: 0, dy: 0, sx: 1, sy: 1 };

    for (const [index, path] of paths.entries()) {
      path.style.strokeDasharray = `${lengths[index]} ${lengths[index]}`;
    }

    return trackScene("signature", {
      measure(stage) {
        // The ink box inside the drawing, from the viewBox and data-ink the build writes.
        const [vx, vy, vw, vh] = svg.getAttribute("viewBox").split(/\s+/).map(Number);
        const [ix, iy, iw, ih] = svg.dataset.ink.split(/\s+/).map(Number);
        // The figure is centred with the CSS translate property (-50%, -50%), which offsetLeft does
        // not include: move the box to where it is drawn.
        const box = offsetWithin(figure, stage);
        box.x -= box.w / 2;
        box.y -= box.h / 2;
        const inkX = ((ix - vx) / vw) * box.w;
        const inkY = ((iy - vy) / vh) * box.h;
        const inkW = (iw / vw) * box.w;
        const inkH = (ih / vh) * box.h;
        const shot = offsetWithin(image, stage);
        const sx = (SIGNATURE_MARK.w * shot.w) / inkW;
        const sy = (SIGNATURE_MARK.h * shot.h) / inkH;
        landing = {
          sx,
          sy,
          dx: shot.x + SIGNATURE_MARK.x * shot.w - box.x - inkX * sx,
          dy: shot.y + SIGNATURE_MARK.y * shot.h - box.y - inkY * sy,
        };
      },
      update(p) {
        hairline.style.transform = `scaleX(${range(p, 0, 0.08)})`;
        hairline.style.opacity = 1 - range(p, 0.08, 0.2);

        // The one paint property in the page: stroke-dashoffset on two short SVG paths. It draws the
        // line the way a pen would; transform and opacity cannot.
        const drawn = range(p, 0.08, 0.5) * total;
        paths.forEach((path, index) => {
          const before = lengths.slice(0, index).reduce((a, b) => a + b, 0);
          path.style.strokeDashoffset = lengths[index] - clamp01((drawn - before) / lengths[index]) * lengths[index];
        });

        const land = easeInOutCubic(range(p, 0.58, 0.84));
        setStyle(render, `scale(${mix(1.06, 1, land)})`, range(p, 0.58, 0.84));
        setStyle(figure,
          `translate3d(${landing.dx * land}px, ${landing.dy * land}px, 0) scale(${mix(1, landing.sx, land)}, ${mix(1, landing.sy, land)})`,
          1 - range(p, 0.84, 0.92));
        const appear = range(p, 0.84, 0.92);
        for (const element of fadeIn) setStyle(element, `translate3d(0, ${mix(1, 0, appear)}rem, 0)`, appear);
      },
      reset() {
        for (const element of [hairline, figure, render, ...fadeIn]) setStyle(element);
        for (const path of paths) path.style.strokeDashoffset = "";
      },
    });
  }

  // ---------------------------------------------------------------- the engine

  function startScenes() {
    const scenes = [
      heroScene(), wordsScene(), designScene(), settleScene("details", 1, 0.5, 1.08), lightScene(),
      explodedScene(), settleScene("inside", 1, 0.3, 1.06), boardScene(), firmwareScene(), signatureScene(),
    ].filter(Boolean);
    const live = new Set();
    let queued = false;
    let running = true;

    const render = () => {
      queued = false;
      if (!running) return;
      const y = scrollY;
      for (const scene of live) {
        if (scene.enabled) scene.update(scene.progress(y));
      }
    };
    const request = () => {
      if (!queued) {
        queued = true;
        requestAnimationFrame(render);
      }
    };
    // Every scene is set to its state for the current scroll position, near or not, so nothing
    // flashes in a resting state before the observer reports it.
    const measure = () => {
      for (const scene of scenes) {
        scene.reset();
        scene.measure();
      }
      if (frames) return showFrames();
      const y = scrollY;
      for (const scene of scenes) {
        if (scene.enabled) scene.update(scene.progress(y));
      }
    };
    const showFrames = () => {
      for (const scene of scenes) {
        const p = scene.id in frames.named ? frames.named[scene.id] : frames.all;
        if (p === null || p === undefined || !scene.enabled) continue;
        if (scene.progressOf) scene.update(0, p);
        else scene.update(p);
      }
    };

    if (!frames) {
      const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          const scene = scenes.find((s) => s.observed === entry.target);
          if (entry.isIntersecting) {
            live.add(scene);
            scene.section.classList.add("is-live");
          } else if (live.has(scene)) {
            // Leave the scene at its clamped end state before it stops updating.
            if (scene.enabled) scene.update(scene.progress(scrollY));
            live.delete(scene);
            scene.section.classList.remove("is-live");
          }
        }
        request();
      }, { rootMargin: "50% 0px" });
      for (const scene of scenes) observer.observe(scene.observed);
      addEventListener("scroll", request, { passive: true });
    }

    new ResizeObserver(measure).observe(root);
    addEventListener("load", measure);
    if (document.fonts) document.fonts.ready.then(measure);
    measure();

    return () => {
      running = false;
      removeEventListener("scroll", request);
      for (const scene of scenes) {
        scene.reset();
        scene.section.classList.remove("is-live");
      }
    };
  }

  // ---------------------------------------------------------------- widgets (user-driven only)

  function colourways() {
    const figure = document.querySelector(".colourway");
    if (!figure) return;
    const group = figure.querySelector(".finishes");
    const picture = figure.querySelector("picture");
    const caption = figure.querySelector(".finish-caption");
    const buttons = [...group.querySelectorAll("button")];
    const choose = (button) => {
      const quadrant = Number(button.dataset.quadrant);
      picture.style.setProperty("--qx", quadrant % 2 ? "-50%" : "0%");
      picture.style.setProperty("--qy", quadrant > 1 ? "-50%" : "0%");
      for (const other of buttons) other.setAttribute("aria-pressed", String(other === button));
      caption.textContent = `Showing ${button.dataset.name}, ${button.dataset.kind}. Finishes are proposals; nothing has been printed or milled.`;
    };
    for (const button of buttons) button.addEventListener("click", () => choose(button));
    group.hidden = false;
    choose(buttons[0]);
  }

  function boardFlip() {
    const flip = document.querySelector("[data-flip]");
    if (!flip) return;
    const state = { board: "assembled", side: "top" };
    const views = [...flip.querySelectorAll(".flip-view")];
    const buttons = [...flip.querySelectorAll("button")];
    const show = () => {
      for (const view of views) view.classList.toggle("is-shown", view.dataset.view === `${state.board}-${state.side}`);
      for (const button of buttons) {
        const pressed = button.dataset.flipBoard ? button.dataset.flipBoard === state.board : button.dataset.flipSide === state.side;
        button.setAttribute("aria-pressed", String(pressed));
      }
    };
    for (const button of buttons) {
      button.addEventListener("click", () => {
        if (button.dataset.flipBoard) state.board = button.dataset.flipBoard;
        else state.side = button.dataset.flipSide;
        show();
      });
    }
    flip.querySelector(".flip-controls").hidden = false;
    show();
  }

  // Layer browser: the ARIA tabs pattern. Arrow keys move between tabs, Home and End jump.
  function layerTabs() {
    const browser = document.querySelector("[data-tabs]");
    if (!browser) return;
    const list = browser.querySelector('[role="tablist"]');
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    const panels = tabs.map((tab) => document.getElementById(tab.getAttribute("aria-controls")));
    const select = (index, focus) => {
      tabs.forEach((tab, i) => {
        const selected = i === index;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        panels[i].hidden = !selected;
      });
      if (focus) tabs[index].focus();
    };
    panels.forEach((panel, i) => {
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", tabs[i].id);
      panel.tabIndex = 0;
    });
    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => select(i, false));
      tab.addEventListener("keydown", (event) => {
        const last = tabs.length - 1;
        const next = { ArrowRight: i === last ? 0 : i + 1, ArrowLeft: i === 0 ? last : i - 1, Home: 0, End: last }[event.key];
        if (next === undefined) return;
        event.preventDefault();
        select(next, true);
      });
    });
    list.hidden = false;
    select(0, false);
  }

  // The demo GIF (2.6 MB) is fetched only when asked for, and can be paused (WCAG 2.2.2).
  function demo() {
    const figure = document.querySelector("[data-demo]");
    if (!figure) return;
    const image = figure.querySelector(".demo-image");
    const button = figure.querySelector(".demo-play");
    const poster = image.getAttribute("src");
    const posterAlt = image.alt;
    let playing = false;
    button.addEventListener("click", () => {
      playing = !playing;
      image.src = playing ? figure.dataset.gif : poster;
      image.alt = playing
        ? "Animated simulator frames of the demo session: the pad from above, its display, its side LEDs and the USB reports the computer would receive."
        : posterAlt;
      button.textContent = playing ? "Pause the demo" : "Play the demo";
    });
    button.hidden = false;
  }

  // ---------------------------------------------------------------- start

  applyDebug();
  colourways();
  boardFlip();
  layerTabs();
  demo();

  let stopScenes = root.classList.contains("motion") ? startScenes() : null;
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches && stopScenes) {
      root.classList.remove("motion");
      stopScenes();
      stopScenes = null;
    } else if (!reducedMotion.matches && !stopScenes && !params.has("motion")) {
      root.classList.add("motion");
      stopScenes = startScenes();
    }
  });
})();
