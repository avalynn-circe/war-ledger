/* The Ukraine War Ledger: shared page behaviour.
   1. Category toggles in the header apply to every element with data-cat on
      every page, and the choice is remembered in this browser.
   2. The calendar box says TODAY when the page's date is today in Kyiv.
   3. The wire loads earlier days as you scroll. */
(function () {
  var KEYS = { cat: 'ledger-hidden', src: 'ledger-hidden-src' };
  var hidden = { cat: {}, src: {} };
  try { hidden.cat = JSON.parse(localStorage.getItem(KEYS.cat) || '{}') || {}; } catch (e) { hidden.cat = {}; }
  try { hidden.src = JSON.parse(localStorage.getItem(KEYS.src) || '{}') || {}; } catch (e) { hidden.src = {}; }

  function isOff(el) {
    var c = el.getAttribute('data-cat'), s = el.getAttribute('data-src');
    return (c && hidden.cat[c]) || (s && hidden.src[s]) ? true : false;
  }
  function applyToggles() {
    var items = document.querySelectorAll('main [data-cat], main [data-src]');
    Array.prototype.forEach.call(items, function (el) { el.hidden = isOff(el); });
    // A category section with every entry hidden by source hides too.
    Array.prototype.forEach.call(document.querySelectorAll('main .cat'), function (d) {
      if (d.hidden) return;
      var entries = d.querySelectorAll('li.entry, details.hl');
      var visible = 0;
      Array.prototype.forEach.call(entries, function (li) { if (!li.hidden) visible++; });
      if (entries.length && !visible) d.hidden = true;
    });
    var shown = 0;
    Array.prototype.forEach.call(document.querySelectorAll('main .wire .row[data-cat], main li.entry, main details.hl'), function (el) { if (!el.hidden && !el.closest('[hidden]')) shown++; });
    var count = document.getElementById('shown-count');
    if (count) count.textContent = shown;
    var state = document.getElementById('src-state');
    if (state) {
      var srcChips = document.querySelectorAll('#src-toggles .chip[data-src]');
      var off = 0;
      Array.prototype.forEach.call(srcChips, function (c) { if (hidden.src[c.getAttribute('data-src')]) off++; });
      state.textContent = off ? (srcChips.length - off) + ' of ' + srcChips.length + ' on' : 'all on';
    }
    ['cat', 'src'].forEach(function (kind) {
      Array.prototype.forEach.call(document.querySelectorAll('.toggles .chip[data-' + kind + ']'), function (c) {
        c.setAttribute('aria-pressed', hidden[kind][c.getAttribute('data-' + kind)] ? 'false' : 'true');
      });
      try { localStorage.setItem(KEYS[kind], JSON.stringify(hidden[kind])); } catch (e) {}
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll('.toggles'), function (bar) {
    var kind = bar.id === 'src-toggles' ? 'src' : 'cat';
    bar.addEventListener('click', function (ev) {
      var b = ev.target.closest('button');
      if (!b) return;
      if (b.hasAttribute('data-all')) { hidden[kind] = {}; }
      else if (b.hasAttribute('data-none')) {
        Array.prototype.forEach.call(bar.querySelectorAll('.chip[data-' + kind + ']'), function (c) { hidden[kind][c.getAttribute('data-' + kind)] = true; });
      } else if (b.hasAttribute('data-' + kind)) {
        var k = b.getAttribute('data-' + kind);
        if (hidden[kind][k]) delete hidden[kind][k]; else hidden[kind][k] = true;
      }
      applyToggles();
    });
  });

  /* On phones the source row starts collapsed; the reader's choice is kept. */
  var disclosure = document.getElementById('src-disclosure');
  if (disclosure && window.matchMedia && window.matchMedia('(max-width: 600px)').matches) {
    var want = null;
    try { want = localStorage.getItem('ledger-src-open'); } catch (e) { want = null; }
    disclosure.open = want === '1';
    disclosure.addEventListener('toggle', function () {
      try { localStorage.setItem('ledger-src-open', disclosure.open ? '1' : '0'); } catch (e) {}
    });
  }

  function kyivToday() {
    try {
      return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Kyiv', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    } catch (e) { return new Date().toISOString().slice(0, 10); }
  }
  var box = document.querySelector('.cal-box');
  if (box && box.getAttribute('data-date') === kyivToday()) {
    box.classList.add('today');
    var band = box.querySelector('.cal-weekday');
    if (band) band.textContent = 'TODAY';
  }

  /* Wire: the page holds the newest day; earlier days are fetched as
     fragments (wire-data/<date>.html) while the reader scrolls. */
  var wire = document.querySelector('.wire[data-days]');
  if (wire && 'IntersectionObserver' in window && window.location.protocol !== 'file:') {
    var days = [];
    try { days = JSON.parse(wire.getAttribute('data-days')) || []; } catch (e) { days = []; }
    var sentinel = document.getElementById('wire-more');
    var loading = false;
    function inView(el) { var r = el.getBoundingClientRect(); return r.top < window.innerHeight + 600; }
    function loadNext() {
      if (loading) return;
      if (!days.length) { if (sentinel) sentinel.textContent = 'Start of the ledger.'; return; }
      loading = true;
      var d = days.shift();
      if (sentinel) sentinel.textContent = 'Loading ' + d + '…';
      fetch('wire-data/' + d + '.html', { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.text() : ''; }).then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var rows = doc.querySelectorAll('.row');
        Array.prototype.forEach.call(rows, function (r) { wire.insertBefore(document.importNode(r, true), sentinel); });
        loading = false;
        applyToggles();
        if (sentinel) sentinel.textContent = days.length ? 'Scroll for ' + days[0] : 'Start of the ledger.';
        if (sentinel && inView(sentinel)) loadNext();
      }).catch(function () { loading = false; if (sentinel) sentinel.textContent = 'Could not load ' + d + '.'; });
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) loadNext(); });
    }, { rootMargin: '600px 0px' });
    if (sentinel) io.observe(sentinel);
  }

  applyToggles();
})();
