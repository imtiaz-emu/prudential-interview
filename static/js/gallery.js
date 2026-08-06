(function () {
  const loadingEl = document.getElementById("gallery-loading");
  const gallery = document.getElementById("gallery-grid");

  if (!loadingEl || !gallery) {
    return;
  }

  const images = Array.from(gallery.querySelectorAll("img"));
  if (images.length === 0) {
    loadingEl.classList.add("is-hidden");
    return;
  }

  let completed = 0;

  const markDone = function () {
    completed += 1;
    if (completed >= images.length) {
      loadingEl.classList.add("is-hidden");
    }
  };

  images.forEach(function (img) {
    if (img.complete) {
      markDone();
      return;
    }

    img.addEventListener("load", markDone, { once: true });
    img.addEventListener("error", markDone, { once: true });
  });
})();
