/* The Ukraine War Ledger: shared page behaviour.
   1. Category toggles in the header apply to every element with data-cat on
      every page, and the choice is remembered in this browser.
   2. The calendar box says TODAY when the page's date is today in Kyiv.
   3. The wire loads earlier days as you scroll. */
(function () {
  var KEY = 'ledger-hidden';
  var hidden = {};
  try { hidden = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { hidden = {}; }

  function applyToggles() {
    var chips = document.querySelectorAll('#toggles .chip[data-cat]');
    var items = document.querySelectorAll('main [data-cat]');
    var shown = 0;
    Array.prototype.forEach.call(items, function (el) {
      var off = !!hidden[el.getAttribute('data-cat')];
      el.hidden = off;
      if (!off) shown++;
    });
    Array.prototype.forEach.call(chips, function (c) {
      c.setAttribute('aria-pressed', hidden[c.getAttribute('data-cat')] ? 'false' : 'true');
    });
    var count = document.getElementById('shown-count');
    if (count) count.textContent = shown;
    try { localStorage.setItem(KEY, JSON.stringify(hidden)); } catch (e) {}
  }

  var toggles = document.getElementById('toggles');
  if (toggles) {
    toggles.addEventListener('click', function (ev) {
      var b = ev.target.closest('button');
      if (!b) return;
      if (b.hasAttribute('data-all')) { hidden = {}; }
      else if (b.hasAttribute('data-none')) {
        Array.prototype.forEach.call(toggles.querySelectorAll('.chip[data-cat]'), function (c) { hidden[c.getAttribute('data-cat')] = true; });
      } else if (b.hasAttribute('data-cat')) {
        var k = b.getAttribute('data-cat');
        if (hidden[k]) delete hidden[k]; else hidden[k] = true;
      }
      applyToggles();
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
