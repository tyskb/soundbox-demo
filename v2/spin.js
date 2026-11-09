// Hero 360°: a pre-rendered Cycles turntable (36 frames per size, blender/render_spin.sh) shown on a canvas.
// Drag / swipe sideways to turn (vertical swipes still scroll), arrow keys step.
// Each frame has a mask (red = shell, green = logo), so the shell colour is applied here on the GPU
// instead of rendering 36 frames x 5 colours.
// Smoothness: the view glides after the finger and cross-fades between neighbouring frames, so turning is
// continuous rather than 10° jumps. Frames are decoded off the main thread (createImageBitmap) and
// uploaded to the GPU at most one per animation frame; turning then only swaps textures. The page colour
// is multiplied in the shader (no CSS blend mode for Chrome to recomposite).
(function () {
  'use strict';
  var F = 36;
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var VS = 'attribute vec2 p;varying vec2 v;void main(){v=vec2(p.x*.5+.5,.5-p.y*.5);gl_Position=vec4(p,0.,1.);}';
  var FS = [
    'precision mediump float;',
    'uniform sampler2D uA,uMA,uB,uMB;uniform vec3 uRatio,uBg;uniform float uLogo,uT;varying vec2 v;',
    'vec3 shade(sampler2D img,sampler2D msk){',
    '  vec3 b=pow(texture2D(img,v).rgb,vec3(2.2));',              // to linear
    '  vec3 m=texture2D(msk,v).rgb;',
    '  vec3 o=mix(b,b*(uRatio*.955+.045),m.r);',                    // shell: albedo swap, keep a little clear-coat sheen
    '  return mix(o,vec3(.62),m.g*uLogo);',                         // light logo on dark shells
    '}',
    'void main(){',
    '  vec3 o=mix(shade(uA,uMA),shade(uB,uMB),uT);',                // blend neighbouring frames
    '  gl_FragColor=vec4(pow(o,vec3(1./2.2))*uBg,1.);',             // white studio backdrop -> page colour
    '}'].join('\n');

  function srgb(h) { return [1, 3, 5].map(function (i) { return parseInt(h.substr(i, 2), 16) / 255; }); }
  function lin(h) { return srgb(h).map(function (c) { return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }); }
  var WHITE = lin('#ecebe6');

  function Spin(fig, base) {
    var canvas = document.createElement('canvas');
    canvas.className = 'spin';
    canvas.tabIndex = 0;
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', '360° 檢視：拖動或者用左右鍵轉');
    var gl = canvas.getContext('webgl', { alpha: false, antialias: false, depth: false, stencil: false, failIfMajorPerformanceCaveat: true });
    if (!gl) return null;   // no GPU (software WebGL would stutter): the page keeps the still images
    var dbg = gl.getExtension('WEBGL_debug_renderer_info');
    if (dbg && /swiftshader|llvmpipe|software|basic render/i.test(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL))) return null;
    var prog = gl.createProgram();
    [[gl.VERTEX_SHADER, VS], [gl.FRAGMENT_SHADER, FS]].forEach(function (s) {
      var sh = gl.createShader(s[0]); gl.shaderSource(sh, s[1]); gl.compileShader(sh); gl.attachShader(prog, sh);
    });
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return null;
    gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(prog, 'p');
    gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    ['uA', 'uMA', 'uB', 'uMB'].forEach(function (n, u) { gl.uniform1i(gl.getUniformLocation(prog, n), u); });
    var uRatio = gl.getUniformLocation(prog, 'uRatio'), uLogo = gl.getUniformLocation(prog, 'uLogo'), uT = gl.getUniformLocation(prog, 'uT');
    var bg = srgb(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#eeece6');
    gl.uniform3f(gl.getUniformLocation(prog, 'uBg'), bg[0], bg[1], bg[2]);

    function texture(src) {
      var t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T].forEach(function (w) { gl.texParameteri(gl.TEXTURE_2D, w, gl.CLAMP_TO_EDGE); });
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, src);
      return t;
    }
    function bitmap(img, w) {   // decode (and shrink to what the canvas needs) off the main thread
      if (!window.createImageBitmap) return Promise.resolve(img);
      var h = Math.round(w * img.naturalHeight / img.naturalWidth);
      return createImageBitmap(img, { resizeWidth: w, resizeHeight: h, resizeQuality: 'medium' })
        .catch(function () { return createImageBitmap(img); }).catch(function () { return img; });
    }
    var dpr = Math.min(devicePixelRatio || 1, 2);
    var texW = function () { return Math.max(480, Math.min(1000, Math.round((canvas.clientWidth || 600) * dpr))); };

    var size = null, sets = {}, colour = WHITE, logo = 0, touched = false, ready = false;
    var pos = 0, target = 0, loop = 0, dirty = true;   // pos/target: fractional frame index, unbounded
    var pad = function (i) { return (i < 10 ? '0' : '') + i; };
    var wrap = function (i) { return ((i % F) + F) % F; };

    // ---- loading: images -> bitmaps (off-thread) -> one GPU upload per animation frame
    var uploads = [], pumping = 0;
    function pump() {
      pumping = 0;
      var u = uploads.shift(); if (!u) return;
      if (!u.set.dead) {
        u.set.tex[u.i] = texture(u.bm[0]); u.set.mask[u.i] = texture(u.bm[1]);
        if (++u.set.count === F && !nudged) { nudged = true; setTimeout(nudge, 400); }
        if (u.n === size) { if (!ready && u.i === 0) first(); else dirty = true; go(); }
      }
      u.bm.forEach(function (b) { if (b && b.close) b.close(); });
      if (uploads.length) pumping = requestAnimationFrame(pump);
    }
    // First paint needs frame 0 only. The other 35 wait until the page is idle (or the moment someone drags),
    // so the first seconds aren't spent decoding 70 images next to the page and its fonts.
    var idleGate = new Promise(function (go) {
      var later = function () { setTimeout(function () { (window.requestIdleCallback || setTimeout)(go, { timeout: 2500 }); }, 1200); };
      if (document.readyState === 'complete') later(); else addEventListener('load', later, { once: true });
      canvas.addEventListener('pointerdown', go, { once: true });
      canvas.addEventListener('keydown', go, { once: true });
    });
    function load(n) {   // frame 0 first, then outwards both ways, two at a time
      var set = sets[n] = { tex: [], mask: [], dead: false, count: 0 };
      var order = [0]; for (var k = 1; k <= F / 2; k++) { order.push(k % F); if (k !== F / 2) order.push((F - k) % F); }
      var next = 0;
      function one() {
        if (set.dead || next >= order.length) return;
        if (next === 1 && !set.released) { set.released = true; idleGate.then(function () { one(); one(); }); return; }
        var i = order[next++], left = 2, a = new Image(), m = new Image();
        var done = function () {
          if (--left) return;
          var w = texW();
          Promise.all([bitmap(a, w), bitmap(m, Math.round(w / 2))]).then(function (bm) {
            uploads.push({ set: set, n: n, i: i, bm: bm });
            if (!pumping) pumping = requestAnimationFrame(pump);
            one();
          });
        };
        a.onload = m.onload = done;
        a.onerror = m.onerror = function () { one(); };
        a.src = base + n + '/' + pad(i) + '.jpg'; m.src = base + n + '/m' + pad(i) + '.png';
      }
      one();
    }
    function drop(n) {   // free the GPU memory of a size we left
      var set = sets[n]; if (!set) return;
      set.dead = true;
      set.tex.concat(set.mask).forEach(function (t) { if (t) gl.deleteTexture(t); });
      delete sets[n];
    }
    var nudged = false;
    function first() { ready = true; resize(); fig.classList.add('spinning'); }

    function nearest(set, i) {   // closest frame already on the GPU
      for (var d = 0; d <= F / 2; d++) {
        var a = wrap(i + d), b = wrap(i - d);
        if (set.tex[a]) return a; if (set.tex[b]) return b;
      }
      return -1;
    }
    function draw() {
      var set = sets[size]; if (!set || !ready) return;
      var f = Math.floor(pos), t = pos - f, a = wrap(f), b = wrap(f + 1);
      if (!set.tex[a] || !set.tex[b]) { a = b = nearest(set, Math.round(pos)); t = 0; }   // still loading
      if (a < 0) return;
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, set.tex[a]);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, set.mask[a]);
      gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, set.tex[b]);
      gl.activeTexture(gl.TEXTURE3); gl.bindTexture(gl.TEXTURE_2D, set.mask[b]);
      gl.uniform3f(uRatio, colour[0], colour[1], colour[2]);
      gl.uniform1f(uLogo, logo);
      gl.uniform1f(uT, t);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    var last = 0;
    function tick(now) {   // glide pos toward target; draw only when something changed
      loop = 0;
      var dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
      var d = target - pos;
      if (Math.abs(d) > 0.002) { pos += d * (reduce ? 1 : 1 - Math.exp(-dt * 18)); dirty = true; } else if (pos !== target) { pos = target; dirty = true; }
      if (dirty) { dirty = false; draw(); }
      if (pos !== target || coasting) loop = requestAnimationFrame(tick); else last = 0;
    }
    function go() { if (!loop) loop = requestAnimationFrame(tick); }
    function resize() {
      var w = Math.round(canvas.clientWidth * dpr);
      if (!w) return;
      var cw = Math.min(w, 1000);
      if (cw !== canvas.width) { canvas.width = cw; canvas.height = Math.round(cw * 0.75); gl.viewport(0, 0, canvas.width, canvas.height); }
      dirty = true; go();
    }
    new ResizeObserver(resize).observe(canvas);

    // ---- turning
    var x0 = null, t0 = 0, vel = 0, lastX = 0, lastT = 0, coasting = false;
    var step = function () { return Math.max(6, canvas.clientWidth / 40); };   // px per frame
    function interact() { if (!touched) { touched = true; fig.classList.add('touched'); } coasting = false; }
    canvas.addEventListener('pointerdown', function (e) {
      interact(); x0 = lastX = e.clientX; lastT = performance.now(); t0 = target; vel = 0;
      try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* synthetic events */ }
    });
    canvas.addEventListener('pointermove', function (e) {
      if (x0 === null) return;
      var now = performance.now();
      vel = (e.clientX - lastX) / Math.max(1, now - lastT); lastX = e.clientX; lastT = now;
      target = t0 + (e.clientX - x0) / step();         // drag right = the front swings right
      go();
    });
    function release() {
      if (x0 === null) return; x0 = null;
      if (reduce || Math.abs(vel) < 0.15) { target = Math.round(target); go(); return; }   // settle on a real frame
      var v = vel * 16 / step(); coasting = true;
      (function coast() {
        if (!coasting) return;
        v *= 0.93; target += v;
        if (Math.abs(v) > 0.03) requestAnimationFrame(coast); else { coasting = false; target = Math.round(target); }
        go();
      })();
    }
    canvas.addEventListener('pointerup', release);
    canvas.addEventListener('pointercancel', release);
    canvas.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { interact(); target = Math.round(target) + (e.key === 'ArrowRight' ? 1 : -1); go(); e.preventDefault(); }
    });
    function nudge() {   // one small swing so people see it turns
      if (reduce || touched) return;
      target = 3; go();
      setTimeout(function () { if (!touched) { target = 0; go(); } }, 700);
    }

    fig.appendChild(canvas);
    return {
      setSize: function (n) { if (n === size) return; if (size) drop(size); size = n; pos = target = Math.round(target); load(n); },
      setColour: function (hex) { var c = lin(hex); colour = [c[0] / WHITE[0], c[1] / WHITE[1], c[2] / WHITE[2]]; logo = c[0] + c[1] + c[2] < 0.7 ? 1 : 0; dirty = true; go(); }
    };
  }
  window.Spin = Spin;
})();
