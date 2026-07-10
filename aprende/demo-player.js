/* ============================================================
   Aprende OneTrack — demo-player.js
   Motor de demos guiadas: recrea la UI de OneTrack en HTML/CSS
   y la recorre con un dedo (touch) animado + captions por paso.
   Declarativo: cada tutorial define un guion de pasos; el motor
   se encarga del touch, timing, controles y replay.
   Sin dependencias. Vanilla JS.
   (Portado del motor de Aprende Residy; cursor flecha → touch.)
   ============================================================ */
(function () {
  'use strict';

  var REDUCE = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function DemoPlayer(root, opts) {
    this.root = typeof root === 'string' ? document.querySelector(root) : root;
    if (!this.root) return;
    this.steps = opts.steps || [];
    this.autoplay = opts.autoplay !== false;
    this.token = 0;        // invalida corridas anteriores al reiniciar
    this.paused = false;
    this.ff = false;       // fast-forward (botón siguiente)
    this.started = false;
    this.finished = false;
    this._build();
    this._observe();
  }

  /* ---- construcción del chrome del player ---- */
  DemoPlayer.prototype._build = function () {
    var r = this.root;
    this.tpl = r.querySelector('template');
    this.stage = r.querySelector('.dp-stage');

    // pantalla (se reconstruye en cada replay desde el template)
    this.screen = document.createElement('div');
    this.screen.className = 'dp-screen';
    this.stage.appendChild(this.screen);

    // dedo falso (indicador touch, no cursor de mouse: la app es iOS)
    this.cursor = document.createElement('div');
    this.cursor.className = 'dp-cursor';
    this.stage.appendChild(this.cursor);

    // toast
    this.toastEl = document.createElement('div');
    this.toastEl.className = 'dp-toast';
    this.stage.appendChild(this.toastEl);

    // overlay de inicio / replay
    this.overlay = document.createElement('div');
    this.overlay.className = 'dp-overlay';
    this.overlay.innerHTML = '<button class="dp-bigplay" aria-label="Reproducir demo"><svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l13-7.5L7 4.5z"/></svg><span>Ver demo</span></button>';
    this.stage.appendChild(this.overlay);

    // barra: caption + dots + controles
    var bar = r.querySelector('.dp-bar');
    this.captionEl = bar.querySelector('.dp-caption');
    this.stepnumEl = bar.querySelector('.dp-stepnum');
    var dots = bar.querySelector('.dp-dots');
    this.dots = [];
    for (var i = 0; i < this.steps.length; i++) {
      var d = document.createElement('i');
      dots.appendChild(d);
      this.dots.push(d);
    }
    var self = this;
    bar.querySelector('[data-dp="play"]').addEventListener('click', function () { self.togglePause(); });
    bar.querySelector('[data-dp="next"]').addEventListener('click', function () { self.ff = true; });
    bar.querySelector('[data-dp="restart"]').addEventListener('click', function () { self.restart(); });
    this.playBtn = bar.querySelector('[data-dp="play"]');
    this.overlay.querySelector('.dp-bigplay').addEventListener('click', function () { self.restart(); });

    this._reset();
  };

  DemoPlayer.prototype._reset = function () {
    this.screen.innerHTML = '';
    this.screen.appendChild(this.tpl.content.cloneNode(true));
    this.cursor.style.left = '55%';
    this.cursor.style.top = '70%';
    this.cursor.style.opacity = '0';
    this.toastEl.classList.remove('on');
    this.captionEl.textContent = this.root.getAttribute('data-intro') || 'Presiona ▶ para ver la demo.';
    if (this.stepnumEl) this.stepnumEl.textContent = '·';
    this._mark(-1);
  };

  DemoPlayer.prototype._mark = function (idx) {
    this.dots.forEach(function (d, i) {
      d.className = i < idx ? 'done' : (i === idx ? 'on' : '');
    });
  };

  /* ---- autoplay al entrar al viewport ---- */
  DemoPlayer.prototype._observe = function () {
    if (!this.autoplay || !('IntersectionObserver' in window)) return;
    var self = this;
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (e) {
        if (e.isIntersecting && !self.started) {
          self.started = true;
          io.disconnect();
          setTimeout(function () { self.restart(); }, 350);
        }
      });
    }, { threshold: 0.45 });
    io.observe(this.stage);
  };

  /* ---- utilidades de corrida ---- */
  DemoPlayer.prototype.q = function (sel) { return this.screen.querySelector(sel); };

  DemoPlayer.prototype.sleep = function (ms, tok) {
    var self = this;
    if (REDUCE || this.ff) ms = 0;
    return new Promise(function (res, rej) {
      var t0 = performance.now();
      (function tick(now) {
        if (tok !== self.token) return rej('stale');
        if (self.paused) { requestAnimationFrame(tick); return; }
        if (self.ff || (now - t0) >= ms) return res();
        requestAnimationFrame(tick);
      })(t0);
    });
  };

  DemoPlayer.prototype.moveTo = function (sel, tok) {
    var el = this.q(sel);
    if (!el) return Promise.resolve();
    var sr = this.stage.getBoundingClientRect();
    var r = el.getBoundingClientRect();
    var x = r.left - sr.left + r.width / 2;
    var y = r.top - sr.top + r.height / 2;
    this.cursor.style.opacity = '1';
    this.cursor.style.left = x + 'px';
    this.cursor.style.top = y + 'px';
    return this.sleep(REDUCE ? 0 : 500, tok);
  };

  DemoPlayer.prototype.press = function (sel, tok) {
    var el = this.q(sel);
    var self = this;
    this.cursor.classList.add('tap');
    if (el) el.classList.add('dp-press');
    return this.sleep(190, tok).then(function () {
      self.cursor.classList.remove('tap');
      if (el) el.classList.remove('dp-press');
      return self.sleep(120, tok);
    });
  };

  DemoPlayer.prototype.typeIn = function (sel, text, tok) {
    var el = this.q(sel);
    if (!el) return Promise.resolve();
    var self = this;
    el.textContent = '';
    el.classList.add('dp-caret');
    var i = 0;
    function next() {
      if (i >= text.length) { el.classList.remove('dp-caret'); return Promise.resolve(); }
      el.textContent += text.charAt(i++);
      return self.sleep(42, tok).then(next);
    }
    return next();
  };

  DemoPlayer.prototype.toast = function (text, tok) {
    var self = this;
    this.toastEl.textContent = text;
    this.toastEl.classList.add('on');
    return this.sleep(1200, tok).then(function () { self.toastEl.classList.remove('on'); });
  };

  /* aplica clases: "+clase -otra" sobre el selector */
  DemoPlayer.prototype.cls = function (sel, spec) {
    var el = this.q(sel);
    if (!el) return;
    spec.split(/\s+/).forEach(function (t) {
      if (t.charAt(0) === '+') el.classList.add(t.slice(1));
      else if (t.charAt(0) === '-') el.classList.remove(t.slice(1));
    });
  };

  /* ---- ejecuta una acción [tipo, ...args] ---- */
  DemoPlayer.prototype._run = function (a, tok) {
    switch (a[0]) {
      case 'move':   return this.moveTo(a[1], tok);
      case 'click':  var self = this; return this.moveTo(a[1], tok).then(function () { return self.press(a[1], tok); });
      case 'type':   return this.typeIn(a[1], a[2], tok);
      case 'text':   var el = this.q(a[1]); if (el) el.textContent = a[2]; return Promise.resolve();
      case 'show':   this.cls(a[1], '-g'); return Promise.resolve();
      case 'hide':   this.cls(a[1], '+g'); return Promise.resolve();
      case 'cls':    this.cls(a[1], a[2]); return Promise.resolve();
      case 'wait':   return this.sleep(a[1], tok);
      case 'toast':  return this.toast(a[1], tok);
      case 'hidecursor': this.cursor.style.opacity = '0'; return Promise.resolve();
      default:       return Promise.resolve();
    }
  };

  DemoPlayer.prototype.restart = function () {
    this.token++;
    this.paused = false;
    this.ff = false;
    this.finished = false;
    this.overlay.classList.remove('on');
    this._setPlayIcon(true);
    this._reset();
    this.play(this.token);
  };

  DemoPlayer.prototype.togglePause = function () {
    if (this.finished) { this.restart(); return; }
    this.paused = !this.paused;
    this._setPlayIcon(!this.paused);
  };

  DemoPlayer.prototype._setPlayIcon = function (playing) {
    this.playBtn.innerHTML = playing
      ? '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="4" width="5" height="16" rx="1"/><rect x="14" y="4" width="5" height="16" rx="1"/></svg>'
      : '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l13-7.5L7 4.5z"/></svg>';
  };

  DemoPlayer.prototype.play = function (tok) {
    var self = this;
    var chain = Promise.resolve();
    this.steps.forEach(function (step, si) {
      chain = chain.then(function () {
        if (tok !== self.token) throw 'stale';
        self.ff = false;
        self._mark(si);
        if (self.stepnumEl) self.stepnumEl.textContent = (si + 1) + ' / ' + self.steps.length;
        self.captionEl.classList.remove('in');
        void self.captionEl.offsetWidth; // reinicia la animación del caption
        self.captionEl.textContent = step.caption;
        self.captionEl.classList.add('in');
        var inner = Promise.resolve();
        step.run.forEach(function (a) {
          inner = inner.then(function () {
            if (tok !== self.token) throw 'stale';
            return self._run(a, tok);
          });
        });
        return inner.then(function () { return self.sleep(step.hold != null ? step.hold : 1150, tok); });
      });
    });
    chain.then(function () {
      if (tok !== self.token) return;
      self.finished = true;
      self._mark(self.steps.length);
      self.cursor.style.opacity = '0';
      self.overlay.classList.add('on');
      self.overlay.querySelector('.dp-bigplay span').textContent = 'Repetir demo';
      self._setPlayIcon(false);
    }).catch(function (e) { if (e !== 'stale') throw e; });
  };

  window.DemoPlayer = DemoPlayer;
})();
