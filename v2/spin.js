// Hero 360°: a pre-rendered Cycles turntable (36 frames per size, blender/render_spin.sh) shown on a canvas.
// Drag / swipe sideways to turn (vertical swipes still scroll), arrow keys step.
// Each frame has a mask (red = shell, green = logo), so the shell colour is applied here on the GPU
// instead of rendering 36 frames x 5 colours.
// Speed: frames are decoded off the main thread (createImageBitmap), uploaded to the GPU once at canvas
// size, and turning only swaps textures; draws are coalesced to one per animation frame; the page
// background is multiplied in the shader (no CSS blend mode for Chrome to recomposite).
(function () {
  'use strict';
  var F = 36;
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var VS = 'attribute vec2 p;varying vec2 v;void main(){v=vec2(p.x*.5+.5,.5-p.y*.5);gl_Position=vec4(p,0.,1.);}';
  var FS = [
    'precision mediump float;',
    'uniform sampler2D uImg,uMask;uniform vec3 uRatio,uBg;uniform float uLogo;varying vec2 v;',
    'void main(){',
    '  vec3 b=pow(texture2D(uImg,v).rgb,vec3(2.2));',            // to linear
    '  vec3 m=texture2D(uMask,v).rgb;',
    '  vec3 o=mix(b,b*(uRatio*.955+.045),m.r);',                  // shell: albedo swap, keep a little clear-coat sheen
    '  o=mix(o,vec3(.62),m.g*uLogo);',                            // light logo on dark shells
    '  gl_FragColor=vec4(pow(o,vec3(1./2.2))*uBg,1.);',           // white studio backdrop -> page colour
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
    var gl = canvas.getContext('webgl', { alpha: false, antialias: false, depth: false, stencil: false });
    if (!gl) return null;
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
    gl.uniform1i(gl.getUniformLocation(prog, 'uImg'), 0);
    gl.uniform1i(gl.getUniformLocation(prog, 'uMask'), 1);
    var uRatio = gl.getUniformLocation(prog, 'uRatio'), uLogo = gl.getUniformLocation(prog, 'uLogo');
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
      return createImageBitmap(img, { resizeWidth: w, resizeHeight: h, resizeQuality: 'high' })
        .catch(function () { return createImageBitmap(img); }).catch(function () { return img; });
    }
    var dpr = Math.min(devicePixelRatio || 1, 2);
    var texW = function () { return Math.max(480, Math.min(1000, Math.round((canvas.clientWidth || 600) * dpr))); };

    var size = null, sets = {}, idx = 0, colour = WHITE, logo = 0, touched = false, onReady = null, ready = false, raf = 0;
    var pad = function (i) { return (i < 10 ? '0' : '') + i; };

    function load(n) {   // frame 0 first, then outwards both ways, a few at a time
      var set = sets[n] = { tex: [], mask: [], dead: false };
      var order = [0]; for (var k = 1; k <= F / 2; k++) { order.push(k % F); if (k !== F / 2) order.push((F - k) % F); }
      var next = 0;
      function one() {
        if (set.dead || next >= order.length) return;
        var i = order[next++], left = 2, a = new Image(), m = new Image();
        var done = function () {
          if (--left) return;
          var w = texW();
          Promise.all([bitmap(a, w), bitmap(m, Math.round(w / 2))]).then(function (bm) {
            if (!set.dead) {
              set.tex[i] = texture(bm[0]); set.mask[i] = texture(bm[1]);
              if (n === size) { if (!ready && i === 0) first(); else if (i === idx || set.tex[idx] === undefined) schedule(); }
            }
            bm.forEach(function (b) { if (b && b.close) b.close(); });
            one();
          });
        };
        a.onload = m.onload = done;
        a.onerror = m.onerror = function () { one(); };
        a.src = base + n + '/' + pad(i) + '.jpg'; m.src = base + n + '/m' + pad(i) + '.png';
      }
      one(); one(); one();
    }
    function drop(n) {   // free the GPU memory of a size we left
      var set = sets[n]; if (!set) return;
      set.dead = true;
      set.tex.concat(set.mask).forEach(function (t) { if (t) gl.deleteTexture(t); });
      delete sets[n];
    }
    function first() { ready = true; resize(); fig.classList.add('spinning'); if (onReady) onReady(); nudge(); }

    function nearest(set, i) {   // closest frame already on the GPU
      for (var d = 0; d <= F / 2; d++) {
        var a = (i + d) % F, b = (i - d + F) % F;
        if (set.tex[a]) return a; if (set.tex[b]) return b;
      }
      return -1;
    }
    function draw() {
      raf = 0;
      var set = sets[size]; if (!set || !ready) return;
      var i = nearest(set, idx); if (i < 0) return;
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, set.tex[i]);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, set.mask[i]);
      gl.uniform3f(uRatio, colour[0], colour[1], colour[2]);
      gl.uniform1f(uLogo, logo);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    function schedule() { if (!raf) raf = requestAnimationFrame(draw); }
    function resize() {
      var w = Math.round(canvas.clientWidth * dpr);
      if (!w) return;
      canvas.width = Math.min(w, 1000); canvas.height = Math.round(canvas.width * 0.75);
      gl.viewport(0, 0, canvas.width, canvas.height); draw();
    }
    new ResizeObserver(resize).observe(canvas);

    // ---- turning
    var x0 = null, i0 = 0, vel = 0, lastX = 0, lastT = 0, spinRaf = 0;
    var step = function () { return Math.max(6, canvas.clientWidth / 40); };   // px per frame
    function set(i) { var n = ((Math.round(i) % F) + F) % F; if (n !== idx) { idx = n; schedule(); } }
    function interact() { if (!touched) { touched = true; fig.classList.add('touched'); } cancelAnimationFrame(spinRaf); }
    canvas.addEventListener('pointerdown', function (e) {
      interact(); x0 = lastX = e.clientX; lastT = performance.now(); i0 = idx; vel = 0;
      try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* synthetic events */ }
    });
    canvas.addEventListener('pointermove', function (e) {
      if (x0 === null) return;
      var now = performance.now();
      vel = (e.clientX - lastX) / Math.max(1, now - lastT); lastX = e.clientX; lastT = now;
      set(i0 + (e.clientX - x0) / step());           // drag right = the front swings right
    });
    function release() {
      if (x0 === null) return; x0 = null;
      if (reduce || Math.abs(vel) < 0.15) return;
      var f = idx, v = vel * 16 / step();            // frames per animation frame
      (function coast() { v *= 0.92; f += v; set(f); if (Math.abs(v) > 0.05) spinRaf = requestAnimationFrame(coast); })();
    }
    canvas.addEventListener('pointerup', release);
    canvas.addEventListener('pointercancel', release);
    canvas.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { interact(); set(idx + (e.key === 'ArrowRight' ? 1 : -1)); e.preventDefault(); }
    });
    function nudge() {   // one small swing so people see it turns
      if (reduce || touched) return;
      var t0 = performance.now();
      (function go(t) {
        if (touched) return;
        var k = Math.min(1, (t - t0) / 1600);
        set(Math.sin(k * Math.PI) * 4);
        if (k < 1) spinRaf = requestAnimationFrame(go);
      })(t0);
    }

    fig.appendChild(canvas);
    return {
      setSize: function (n) { if (n === size) return; if (size) drop(size); size = n; idx = 0; load(n); },
      setColour: function (hex) { var c = lin(hex); colour = [c[0] / WHITE[0], c[1] / WHITE[1], c[2] / WHITE[2]]; logo = c[0] + c[1] + c[2] < 0.7 ? 1 : 0; schedule(); },
      onReady: function (fn) { onReady = fn; if (ready) fn(); }
    };
  }
  window.Spin = Spin;
})();
