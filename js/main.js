(function () {
  var menuBtn = document.querySelector(".menu-btn");
  var topbarNav = document.querySelector(".topbar-nav");
  if (menuBtn && topbarNav) {
    menuBtn.addEventListener("click", function () {
      var open = topbarNav.classList.toggle("is-open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });

    document.addEventListener("click", function (e) {
      if (
        topbarNav.classList.contains("is-open") &&
        !topbarNav.contains(e.target) &&
        e.target !== menuBtn
      ) {
        topbarNav.classList.remove("is-open");
        menuBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  var searchInputs = document.querySelectorAll("[data-site-search]");
  if (!searchInputs.length) return;

  var cards = document.querySelectorAll("[data-searchable]");
  var meta = document.querySelector("[data-results-meta]");
  var empty = document.querySelector("[data-no-results]");

  function normalize(text) {
    return (text || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  function runSearch(query) {
    var q = normalize(query);
    var visible = 0;

    cards.forEach(function (card) {
      var hay = normalize(card.getAttribute("data-searchable"));
      var show = !q || hay.indexOf(q) !== -1;
      card.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });

    if (meta) {
      meta.textContent = q
        ? "검색어 \"" + query.trim() + "\" — 약 " + visible + "개 결과"
        : "봄 알레르기·환절기 면역·웰니스 관련 콘텐츠";
    }

    if (empty) {
      empty.classList.toggle("is-hidden", visible > 0 || !q);
    }
  }

  searchInputs.forEach(function (input) {
    input.addEventListener("input", function () {
      runSearch(input.value);
    });

    var form = input.closest("form");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        runSearch(input.value);
        var first = document.querySelector("[data-searchable]:not(.is-hidden) a");
        if (first && normalize(input.value)) first.focus();
      });
    }
  });
})();
