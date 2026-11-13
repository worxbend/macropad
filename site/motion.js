// Motion and small widgets for the macropad page. Plain JavaScript, no dependencies.
//
// Scroll scenes: each scene maps scroll position to a progress p from 0 to 1 and writes only
// transform and opacity (plus one stroke-dashoffset, see the signature scene). Offsets are measured
// on load and on resize, never inside the frame loop, and scenes far from the viewport are skipped.
// Without html.motion (no JavaScript, reduced motion, ?motion=off) nothing here moves anything and
// the CSS shows every scene in its final, readable state.
//
// When everything is set up this script adds html.ready. The script in <head> falls back to the
// no-JavaScript layout if it is missing by DOMContentLoaded.
//
// Debug parameters (read once at start):
//   ?frame=0.5                    every scene at progress 0.5, scrolling ignored
//   ?frame=light:0.3,hero:1       named scenes at the given progress
//   ?only=signature,specs         hide every other section (the header stays)
//   ?motion=off                   the reduced-motion page (also read by the script in <head>)
//   ?debug=bands,sigbox,width,errors  outline the exploded bands and the signature target, report
//                                 anything wider than the window, print script errors on the page
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

  // Lists the elements that reach past the right edge of the window. body clips horizontal
  // overflow, so scrollWidth alone would never report it.
  function overflowReport() {
    const limit = root.clientWidth + 0.5;
    const wide = [];
    for (const element of document.body.querySelectorAll("*")) {
      if (element.closest(".frame, .stage, .plate, .detail .clip, .timeline-scroll, [hidden]")) continue;
      const box = element.getBoundingClientRect();
      if (box.width > 0 && box.right > limit) wide.push(`${element.tagName.toLowerCase()}.${element.className || "-"} ${Math.round(box.right)}`);
    }
    return wide;
  }

  function applyDebug() {
    const only = params.get("only");
    if (only) {
      const keep = new Set(only.split(","));
      for (const section of document.querySelectorAll("main > section, body > footer")) {
        section.hidden = !keep.has(section.id);
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
        const wide = overflowReport();
        badge.textContent = `width ${root.clientWidth}: ` + (wide.length ? `OVERFLOW ${wide.slice(0, 4).join(", ")}` : "ok");
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
    const items = [...section.querySelectorAll(selector)].map((element) => ({ element, top: 0 }));
    const scene = {
      id,
      section,
      observed: section,
      enabled: true,
      view: true,
      measure() {
        for (const item of items) item.top = pageTop(item.element);
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
    let start = 0;
    const section = document.getElementById("hero");
    const copy = section.querySelector('[data-part="copy"]');
    const image = section.querySelector('[data-part="image"]');
    image.style.transformOrigin = "50% 38%";
    return trackScene("hero", {
      measure() {
        // Start where the knob tops sit 8 px under the buttons. The knob tops are 6.4% down the
        // render; scaled 1.22 about 38% of its height, that row lands 0.0055 x the height higher
        // than the top of the unscaled picture.
        start = copy.offsetTop + copy.offsetHeight + 8 + 0.0055 * image.offsetHeight;
      },
      update(p) {
        const move = easeInOutCubic(range(p, 0, 0.75));
        setStyle(image, `translate3d(0, ${mix(start, 0, move)}px, 0) scale(${mix(1.22, 1, move)})`);
        // The copy is gone before the product reaches it. CSS keeps it visible while it holds focus.
        const fade = range(p, 0.1, 0.4);
        setStyle(copy, `translate3d(0, ${mix(0, -8, fade)}vh, 0)`, 1 - fade);
      },
      reset() {
        setStyle(image);
        setStyle(copy);
      },
    });
  }

  // ---- manifesto: phrases light up in reading order; the last one draws its hairline.
  // The dim state is 0.55, which keeps large text at 3:1 or better on chalk and on night.
  function wordsScene() {
    const section = document.getElementById("words");
    const paragraph = section.querySelector('[data-part="manifesto"]');
    const phrases = [...paragraph.children];
    const last = paragraph.querySelector(".manifesto-last");
    return viewScene("words", '[data-part="manifesto"]', 0.85, 0.3, (element, p) => {
      phrases.forEach((phrase, index) => {
        phrase.style.opacity = p === null ? "" : 0.55 + 0.45 * clamp01((p * phrases.length) - index);
      });
      last.style.setProperty("--hairline", p === null ? 1 : clamp01((p * phrases.length) - (phrases.length - 1)));
    });
  }

  // ---- design: the seam reaches out from the side render to the edges of the screen.
  function designScene() {
    const section = document.getElementById("design");
    const seamFrame = section.querySelector(".seam-shot .frame");
    const lines = [...section.querySelectorAll('[data-part="seam"]')];
    let top = 0;
    return {
      id: "design",
      section,
      observed: section,
      enabled: true,
      measure() {
        top = pageTop(seamFrame);
      },
      progress(y) {
        return y;
      },
      update(y, fixed) {
        const p = fixed ?? clamp01((0.75 * innerHeight - (top - y)) / (0.35 * innerHeight));
        for (const line of lines) line.style.transform = `scaleX(${p})`;
      },
      reset() {
        for (const line of lines) setStyle(line);
      },
      view: true,
    };
  }

  // ---- parallax: a picture drifts inside its clipped frame while it crosses the viewport.
  function parallaxScene(id, amount, scale) {
    return viewScene(id, '[data-part="parallax"]', 1, -0.6, (element, p) => {
      setStyle(element, p === null ? null : `translate3d(0, ${mix(amount, -amount, p)}%, 0) scale(${scale})`);
    });
  }

  // ---- close-ups settle from a slight zoom as they come in.
  function settleScene(id, from, to, scaleFrom) {
    return viewScene(id, '[data-part="settle"]', from, to, (element, p) => {
      const target = element.classList.contains("clip") ? element.firstElementChild : element;
      setStyle(target, p === null ? null : `scale(${mix(scaleFrom, 1, p)})`);
    });
  }

  // ---- light: the pad sits nearly dark, the LEDs step on, then the render's own glow takes over.
  function lightScene() {
    const section = document.getElementById("light");
    const veil = section.querySelector('[data-part="veil"]');
    const leds = [...section.querySelectorAll('[data-part="led"]')];
    return trackScene("light", {
      update(p) {
        veil.style.opacity = 0.9 * (1 - range(p, 0.45, 0.8));
        const fade = 1 - range(p, 0.55, 0.8);
        leds.forEach((led, index) => {
          const on = range(p, 0.1 + index * 0.08, 0.18 + index * 0.08);
          setStyle(led, `scaleX(${mix(0.6, 1, on)})`, on * fade);
        });
      },
      reset() {
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
    const stack = section.querySelector(".bands");
    // Offsets at the start, in % of the image height, top group first. They close the gaps without
    // pushing one part through another. The outer groups start early.
    const pushed = [8, 5.5, 0, -4.5, -9];
    const head = [0.05, 0, 0, 0, 0.05];
    return trackScene("exploded", {
      update(p) {
        // The closed stack is seen closer, and the camera pulls back as it opens.
        stack.style.transform = `scale(${mix(1.2, 1, easeInOutCubic(range(p, 0.1, 0.75)))})`;
        bands.forEach((band, index) => {
          const t = easeInOutCubic(range(p, 0.15 - head[index], 0.75));
          band.style.transform = `translate3d(0, ${mix(pushed[index], 0, t)}%, 0)`;
          // Labels stay at full contrast; the marker beside each grows when its band is home.
          labels[index].style.setProperty("--home", range(t, 0.8, 1));
        });
      },
      reset() {
        setStyle(stack);
        for (const band of bands) setStyle(band);
        for (const label of labels) label.style.removeProperty("--home");
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
          // A class, not opacity: the dim names keep full contrast (--on-dark-2) and only the
          // marker beside the current one changes.
          names[index].classList.toggle("is-on", index === shown);
        });
      },
      reset() {
        for (const element of screens) setStyle(element);
        for (const name of names) name.classList.remove("is-on");
      },
    });
  }

  // ---- signature: the hairline arrives, the signature is drawn, flies onto its laser mark, and the
  // camera moves in until the base fills the space beside the text.
  // Measured on underside_aluminium.png (1600 x 1100); re-measure them if `make cad` renders the
  // underside with another camera. MARK: the laser mark, x 437-747, y 531-682. SLAB: the base,
  // x 392-1218, y 172-945. The CSS hides the render's own mark under .sig-patch, so only the drawn,
  // sharp line shows on it.
  const SIGNATURE_MARK = { x: 437 / 1600, y: 531 / 1100, w: 310 / 1600, h: 151 / 1100 };
  const SIGNATURE_SLAB = { x: 392 / 1600, y: 172 / 1100, w: 826 / 1600, h: 773 / 1100 };
  // The close-up stops at 1.8 times, where the render is still sharp, and keeps 6% of the space free
  // on every side.
  const SIGNATURE_MAX_ZOOM = 1.8;
  const SIGNATURE_FILL = 0.88;

  function signatureScene() {
    const section = document.getElementById("signature");
    const hairline = section.querySelector('[data-part="hairline"]');
    const figure = section.querySelector('[data-part="signature"]');
    const svg = figure.querySelector("svg");
    const paths = [...svg.querySelectorAll("path")];
    const render = section.querySelector('[data-part="render"]');
    const image = render.querySelector("img");
    const title = section.querySelector(".scene-title");
    const edition = section.querySelector('[data-part="edition"]');
    const fadeIn = [edition, section.querySelector('[data-part="body"]')];
    const lengths = paths.map((path) => path.getTotalLength());
    const total = lengths.reduce((a, b) => a + b, 0);
    let geometry = null;

    for (const [index, path] of paths.entries()) {
      path.style.strokeDasharray = `${lengths[index]} ${lengths[index]}`;
    }

    // Where the close-up may put the base: beside the text on wide screens, between the title and
    // the edition line on narrow ones, so the text never sits on the render.
    function freeArea(stage, renderBox, wide) {
      if (wide) return { x: renderBox.x, y: 0, w: stage.offsetWidth - renderBox.x, h: stage.offsetHeight };
      const head = offsetWithin(title, stage);
      const top = head.y + head.h;
      return { x: 0, y: top, w: stage.offsetWidth, h: offsetWithin(edition, stage).y - top };
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
        const ink = {
          x: ((ix - vx) / vw) * box.w,
          y: ((iy - vy) / vh) * box.h,
          w: (iw / vw) * box.w,
          h: (ih / vh) * box.h,
        };
        const shot = offsetWithin(image, stage);
        const renderBox = offsetWithin(render, stage);
        const sx = (SIGNATURE_MARK.w * shot.w) / ink.w;
        const sy = (SIGNATURE_MARK.h * shot.h) / ink.h;
        const slab = {
          w: SIGNATURE_SLAB.w * shot.w,
          h: SIGNATURE_SLAB.h * shot.h,
          x: shot.x + (SIGNATURE_SLAB.x + SIGNATURE_SLAB.w / 2) * shot.w,
          y: shot.y + (SIGNATURE_SLAB.y + SIGNATURE_SLAB.h / 2) * shot.h,
        };
        const wide = matchMedia("(min-width: 64rem)").matches; // the same breakpoint as the CSS layout
        const area = freeArea(stage, renderBox, wide);
        geometry = {
          box,
          renderBox,
          anchor: { x: slab.x, y: slab.y },
          goal: { x: area.x + area.w / 2, y: area.y + area.h / 2 },
          zoom: Math.min(SIGNATURE_MAX_ZOOM, (SIGNATURE_FILL * area.w) / slab.w, (SIGNATURE_FILL * area.h) / slab.h),
          land: {
            sx,
            sy,
            dx: shot.x + SIGNATURE_MARK.x * shot.w - box.x - ink.x * sx,
            dy: shot.y + SIGNATURE_MARK.y * shot.h - box.y - ink.y * sy,
          },
        };
      },
      update(p) {
        const { box, renderBox, anchor, goal, land } = geometry;
        hairline.style.transform = `scaleX(${range(p, 0, 0.06)})`;
        hairline.style.opacity = 1 - range(p, 0.06, 0.16);

        // The one paint property in the page: stroke-dashoffset on two short SVG paths. It draws the
        // line the way a pen would; transform and opacity cannot.
        const drawn = range(p, 0.06, 0.42) * total;
        let before = 0;
        paths.forEach((path, index) => {
          path.style.strokeDashoffset = lengths[index] - clamp01((drawn - before) / lengths[index]) * lengths[index];
          before += lengths[index];
        });

        // The render fades in while the drawing flies to its mark. Its own mark is covered, so there
        // is only ever one signature on screen, and the drawing stays on top after it lands.
        const fly = easeInOutCubic(range(p, 0.48, 0.7));
        const shown = easeInOutCubic(range(p, 0.5, 0.62));

        // The close-up: render and drawing scale together about the base's centre and move it to the
        // middle of the free area.
        const near = easeInOutCubic(range(p, 0.72, 0.88));
        const zoom = mix(1, geometry.zoom, near);
        const shiftX = (goal.x - anchor.x) * near;
        const shiftY = (goal.y - anchor.y) * near;
        const along = (x, y) => [anchor.x + zoom * (x - anchor.x) + shiftX, anchor.y + zoom * (y - anchor.y) + shiftY];

        const [rx, ry] = along(renderBox.x, renderBox.y);
        setStyle(render, `translate3d(${rx - renderBox.x}px, ${ry - renderBox.y}px, 0) scale(${zoom})`, shown);

        const [fx, fy] = along(box.x + land.dx * fly, box.y + land.dy * fly);
        setStyle(figure,
          `translate3d(${fx - box.x}px, ${fy - box.y}px, 0) scale(${zoom * mix(1, land.sx, fly)}, ${zoom * mix(1, land.sy, fly)})`);

        const appear = range(p, 0.84, 0.94);
        for (const element of fadeIn) setStyle(element, `translate3d(0, ${mix(1, 0, appear)}rem, 0)`, appear);
      },
      reset() {
        for (const element of [hairline, figure, render, ...fadeIn]) setStyle(element);
        for (const path of paths) path.style.strokeDashoffset = "";
      },
    });
  }

  // ---------------------------------------------------------------- the engine

  // Starts the scroll scenes. Returns a function that stops them and removes every listener and
  // observer it added, so a change to reduced motion leaves nothing behind.
  function startScenes() {
    const scenes = [
      heroScene(), wordsScene(), designScene(), lightScene(), parallaxScene("colourways", 3, 1.06),
      settleScene("details", 1, 0.5, 1.08), explodedScene(), settleScene("inside", 1, 0.3, 1.06),
      parallaxScene("board", 4, 1.09), firmwareScene(), signatureScene(),
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
      if (running && !queued) {
        queued = true;
        requestAnimationFrame(render);
      }
    };
    const showFrames = () => {
      for (const scene of scenes) {
        const p = scene.id in frames.named ? frames.named[scene.id] : frames.all;
        if (p === null || p === undefined || !scene.enabled) continue;
        // A view scene takes the progress as its second argument; a track scene as its only one.
        if (scene.view) scene.update(0, p);
        else scene.update(p);
      }
    };
    // Every scene is set to its state for the current scroll position, near or not, so nothing
    // flashes in a resting state before the observer reports it.
    const measure = () => {
      if (!running) return;
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

    let observer = null;
    if (!frames) {
      observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          const scene = scenes.find((s) => s.observed === entry.target);
          if (entry.isIntersecting) {
            live.add(scene);
            scene.section.classList.add("is-live");
          } else if (live.has(scene)) {
            // Leave the scene at its clamped end state before it stops updating.
            if (running && scene.enabled) scene.update(scene.progress(scrollY));
            live.delete(scene);
            scene.section.classList.remove("is-live");
          }
        }
        request();
      }, { rootMargin: "50% 0px" });
      for (const scene of scenes) observer.observe(scene.observed);
      addEventListener("scroll", request, { passive: true });
    }

    const resizeObserver = new ResizeObserver(measure);
    resizeObserver.observe(root);
    addEventListener("load", measure);
    if (document.fonts) document.fonts.ready.then(measure);
    measure();

    return () => {
      running = false;
      removeEventListener("scroll", request);
      removeEventListener("load", measure);
      resizeObserver.disconnect();
      if (observer) observer.disconnect();
      live.clear();
      for (const scene of scenes) {
        scene.reset();
        scene.section.classList.remove("is-live");
      }
    };
  }

  // ---------------------------------------------------------------- widgets (user-driven only)

  // The phone menu closes when a section is chosen and on Escape; without JavaScript it stays a
  // plain <details>.
  function menu() {
    const details = document.querySelector(".nav-menu");
    if (!details) return;
    const summary = details.querySelector("summary");
    details.addEventListener("click", (event) => {
      if (event.target.closest("a")) details.open = false;
    });
    details.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && details.open) {
        details.open = false;
        summary.focus();
      }
    });
  }

  function colourways() {
    const figure = document.querySelector(".colourway");
    if (!figure) return;
    const group = figure.querySelector(".finishes");
    const picture = figure.querySelector(".colourway-plate picture");
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
    // The first finish is set before the caption becomes a live region, so nothing is announced
    // when the page loads; only a click is.
    // The start position is set without the slide: it is not a change the reader asked for.
    picture.style.transition = "none";
    choose(group.querySelector("[data-start]") || buttons[0]);
    picture.getBoundingClientRect(); // applies the start position before the transition returns
    picture.style.transition = "";
    caption.setAttribute("aria-live", "polite");
  }

  // The header turns dark while a dark section (data-ground="dark") is under it. One observer
  // watches a band as tall as the header at the top of the window; it is rebuilt on resize.
  function headerGround() {
    const header = document.querySelector(".top");
    const grounds = [...document.querySelectorAll('[data-ground="dark"]')];
    if (!header || !grounds.length) return;
    const under = new Set();
    let observer = null;
    const watch = () => {
      if (observer) observer.disconnect();
      under.clear();
      const below = Math.max(0, innerHeight - header.offsetHeight);
      observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) under.add(entry.target);
          else under.delete(entry.target);
        }
        root.classList.toggle("header-dark", under.size > 0);
      }, { rootMargin: `0px 0px -${below}px 0px` });
      for (const ground of grounds) observer.observe(ground);
    };
    let height = innerHeight;
    addEventListener("resize", () => {
      if (innerHeight !== height) {
        height = innerHeight;
        watch();
      }
    });
    watch();
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
  menu();
  headerGround();
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
  root.classList.add("ready");
})();
