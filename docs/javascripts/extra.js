(function () {
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var typingTimer = null;
  var observer = null;
  var scrollBound = false;

  document.documentElement.classList.add("js-anim");

  // Thanh tiến độ cuộn ở đỉnh trang
  function updateProgress() {
    var bar = document.getElementById("scroll-progress");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "scroll-progress";
      document.body.appendChild(bar);
    }
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var ratio = h > 0 ? Math.min(1, Math.max(0, window.scrollY / h)) : 0;
    bar.style.transform = "scaleX(" + ratio + ")";
  }

  function progressBar() {
    updateProgress();
    if (!scrollBound) {
      window.addEventListener("scroll", updateProgress, { passive: true });
      window.addEventListener("resize", updateProgress, { passive: true });
      scrollBound = true;
    }
  }

  // Hiện dần các phần tử khi cuộn tới (không áp dụng lên bảng dài để tránh lỗi ẩn nội dung)
  function reveal() {
    if (observer) observer.disconnect();
    var els = document.querySelectorAll(
      ".reveal, .md-post--excerpt, .md-typeset > h2, .md-typeset > .admonition"
    );
    els.forEach(function (el, i) {
      el.classList.add("reveal");
      if (!el.style.getPropertyValue("--d")) {
        el.style.setProperty("--d", (i % 4) * 0.06 + "s");
      }
    });
    if (reduce || !("IntersectionObserver" in window)) {
      els.forEach(function (el) {
        el.classList.add("in");
      });
      return;
    }
    observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            observer.unobserve(e.target);
          }
        });
      },
      { threshold: 0.02, rootMargin: "0px 0px -20px 0px" }
    );
    els.forEach(function (el) {
      observer.observe(el);
    });
  }

  // Chữ gõ lần lượt ở Hero
  function typer() {
    clearTimeout(typingTimer);
    var el = document.querySelector(".hero .rotator");
    if (!el) return;
    var words = (el.dataset.words || "").split("|").filter(Boolean);
    if (reduce || !words.length) {
      el.textContent = words[0] || "";
      return;
    }
    var w = 0,
      c = words[0].length,
      del = true;
    el.textContent = words[0];
    typingTimer = setTimeout(function tick() {
      var word = words[w];
      c += del ? -1 : 1;
      el.textContent = word.slice(0, c);
      var wait = del ? 38 : 85;
      if (!del && c === word.length) {
        del = true;
        wait = 1600;
      } else if (del && c === 0) {
        del = false;
        w = (w + 1) % words.length;
        wait = 260;
      }
      typingTimer = setTimeout(tick, wait);
    }, 1400);
  }

  // Vệt sáng theo chuột trên thẻ
  function cardGlow() {
    document.querySelectorAll(".card").forEach(function (card) {
      if (card.dataset.glowBound) return;
      card.dataset.glowBound = "1";
      card.addEventListener("pointermove", function (e) {
        var r = card.getBoundingClientRect();
        card.style.setProperty("--mx", e.clientX - r.left + "px");
        card.style.setProperty("--my", e.clientY - r.top + "px");
      });
    });
  }

  // Khôi phục kích thước gốc từ thuộc tính height/width của thẻ <img> (tránh bị CSS height:auto phóng to SVG)
  function fixImages() {
    document
      .querySelectorAll(".md-typeset img[height], .md-typeset img[width]")
      .forEach(function (img) {
        var h = img.getAttribute("height");
        var w = img.getAttribute("width");
        if (h && /^\d+$/.test(h)) {
          img.style.height = h + "px";
          if (!w) img.style.width = "auto";
        }
        if (w && /^\d+$/.test(w)) {
          img.style.width = w + "px";
          img.style.maxWidth = "100%";
          if (!h) img.style.height = "auto";
        }
      });
  }

  function init() {
    fixImages();
    progressBar();
    reveal();
    typer();
    cardGlow();
  }

  // document$ do Material cung cấp: chạy lại sau mỗi lần chuyển trang (navigation.instant)
  if (window.document$) window.document$.subscribe(init);
  else document.addEventListener("DOMContentLoaded", init);
})();
