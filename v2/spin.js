// Hero 360°: a pre-rendered Cycles turntable (36 frames per size, blender/render_spin.sh) shown on a canvas.
// Drag / swipe sideways to turn (vertical swipes still scroll), arrow keys step.
// Each frame has a mask (red = shell, green = logo), so the shell colour is applied here on the GPU
// instead of rendering 36 frames x 5 colours.
(function () {
  'use strict';
  var F = 36;
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var VS = 'attribute vec2 p;varying vec2 v;void main(){v=vec2(p.x*.5+.5,.5-p.y*.5);gl_Position=vec4(p,0.,1.);}';
  var FS = [
    'precision mediump float;',
    'uniform sampler2D uImg,uMask;uniform vec3 uRatio;uniform float uLogo;varying vec2 v;',
    'void main(){',
    '  vec3 b=pow(texture2D(uImg,v).rgb,vec3(2.2));',            // to linear
    '  vec3 m=texture2D(uMask,v).rgb;',
    '  vec3 o=mix(b,b*(uRatio*.955+.045),m.r);',                  // shell: albedo swap, keep a little clear-coat sheen
    '  o=mix(o,vec3(.62),m.g*uLogo);',                            // light logo on dark shells
    '  gl_FragColor=vec4(pow(o,vec3(1./2.2)),1.);',
    '}'].join('\n');

  function lin(h) { return [1, 3, 5].map(function (i) { var c = parseInt(h.substr(i, 2), 16) / 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }); }
  var WHITE = lin('#ecebe6');

  function Spin(fig, base) {
    var canvas = document.createElement('canvas');
    canvas.className = 'spin';
    canvas.tabIndex = 0;
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', '360° 檢視：拖動或者用左右鍵轉');
    var gl = canvas.getContext('webgl', { premultipliedAlpha: false, preserveDrawingBuffer: true });
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
    function tex(unit) {
      var t = gl.createTexture(); gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t);
      [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T].forEach(function (w) { gl.texParameteri(gl.TEXTURE_2D, w, gl.CLAMP_TO_EDGE); });
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      return t;
    }
    var tImg = tex(0), tMask = tex(1);
    gl.uniform1i(gl.getUniformLocation(prog, 'uImg'), 0);
    gl.uniform1i(gl.getUniformLocation(prog, 'uMask'), 1);
    var uRatio = gl.getUniformLocation(prog, 'uRatio'), uLogo = gl.getUniformLocation(prog, 'uLogo');

    var size = null, sets = {}, idx = 0, shown = -1, colour = WHITE, logo = 0, touched = false, onReady = null;
    var pad = function (i) { return (i < 10 ? '0' : '') + i; };

    function load(n) {   // frame 0 first, then the rest a few at a time
      if (sets[n]) return sets[n];
      var set = sets[n] = { img: [], mask: [], ok: [] };
      var order = [0]; for (var k = 1; k <= F / 2; k++) { order.push(k % F); if (k !== F / 2) order.push((F - k) % F); }
      var next = 0;
      function one() {
        if (next >= order.length) return;
        var i = order[next++], left = 2, a = new Image(), m = new Image();
        var done = function () { if (--left) return; set.ok[i] = true; if (n === size) { if (!ready && i === 0) first(); draw(); } one(); };
        a.onload = m.onload = done;
        a.onerror = m.onerror = function () { one(); };
        a.src = base + n + '/' + pad(i) + '.jpg'; m.src = base + n + '/m' + pad(i) + '.png';
        set.img[i] = a; set.mask[i] = m;
      }
      one(); one(); one();
      return set;
    }
    var ready = false;
    function first() { ready = true; resize(); fig.classList.add('spinning'); if (onReady) onReady(); nudge(); }

    function nearest(set, i) {   // closest frame that has arrived
      for (var d = 0; d <= F / 2; d++) {
        var a = (i + d) % F, b = (i - d + F) % F;
        if (set.ok[a]) return a; if (set.ok[b]) return b;
      }
      return -1;
    }
    function draw() {
      var set = sets[size]; if (!set || !ready) return;
      var i = nearest(set, idx); if (i < 0) return;
      if (i !== shown) {
        gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, tImg);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, set.img[i]);
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, tMask);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, set.mask[i]);
        shown = i;
      }
      gl.uniform3f(uRatio, colour[0], colour[1], colour[2]);
      gl.uniform1f(uLogo, logo);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    function resize() {
      var w = Math.round(canvas.clientWidth * Math.min(devicePixelRatio || 1, 2));
      if (!w) return;
      canvas.width = Math.min(w, 1000); canvas.height = Math.round(canvas.width * 0.75);
      gl.viewport(0, 0, canvas.width, canvas.height); shown = -1; draw();
    }
    new ResizeObserver(resize).observe(canvas);

    // ---- turning
    var x0 = null, i0 = 0, vel = 0, lastX = 0, lastT = 0, spinRaf = 0;
    var step = function () { return Math.max(6, canvas.clientWidth / 40); };   // px per frame
    function set(i) { idx = ((Math.round(i) % F) + F) % F; draw(); }
    function interact() { if (!touched) { touched = true; fig.classList.add('touched'); } cancelAnimationFrame(spinRaf); }
    canvas.addEventListener('pointerdown', function (e) {
      interact(); x0 = lastX = e.clientX; lastT = performance.now(); i0 = idx; vel = 0; canvas.setPointerCapture(e.pointerId);
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
      setSize: function (n) { if (n === size) return; size = n; shown = -1; idx = 0; load(n); draw(); },
      setColour: function (hex) { var c = lin(hex); colour = [c[0] / WHITE[0], c[1] / WHITE[1], c[2] / WHITE[2]]; logo = c[0] + c[1] + c[2] < 0.7 ? 1 : 0; draw(); },
      onReady: function (fn) { onReady = fn; if (ready) fn(); }
    };
  }
  window.Spin = Spin;
})();
