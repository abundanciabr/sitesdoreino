(function () {
  "use strict";
  var dialog = document.getElementById("demo-dialog");
  var video = document.getElementById("demo-video");
  var previousFocus;
  function openVideo(event) {
    if (!dialog || !video) return;
    previousFocus = event.currentTarget;
    if (typeof dialog.showModal !== "function") {
      window.location.href = video.querySelector("source").src;
      return;
    }
    dialog.showModal();
    document.body.classList.add("dialog-open");
    video.play().catch(function () {});
  }
  document.querySelectorAll("[data-open-video]").forEach(function (button) {
    button.addEventListener("click", openVideo);
  });
  if (dialog) {
    dialog.querySelector("[data-close-video]").addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("click", function (event) {
      if (event.target !== dialog) return;
      var bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
    dialog.addEventListener("close", function () {
      video.pause();
      document.body.classList.remove("dialog-open");
      if (previousFocus) previousFocus.focus();
    });
  }
  var action = document.querySelector(".mobile-action");
  var offer = document.getElementById("a-oferta");
  if (action && offer && "IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      action.classList.toggle("is-hidden", entries[0].isIntersecting);
    }, { threshold: 0.15 }).observe(offer);
  }
})();
