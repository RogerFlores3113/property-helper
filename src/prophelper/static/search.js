// Search page: the "add something that matters" form shows only the boxes its kind uses.
// Without this script every box is shown with a label that names its kind, so the form still works.
(function () {
  "use strict";
  function apply(form) {
    var sel = form.querySelector("[data-kind-select]");
    if (!sel) { return; }
    var kind = sel.value;
    var parts = form.querySelectorAll("[data-kinds]");
    for (var i = 0; i < parts.length; i++) {
      var kinds = (parts[i].getAttribute("data-kinds") || "").split(/\s+/);
      parts[i].hidden = kinds.indexOf(kind) === -1;
    }
  }
  document.addEventListener("DOMContentLoaded", function () {
    var forms = document.querySelectorAll("form[data-kind-form]");
    for (var i = 0; i < forms.length; i++) {
      (function (form) {
        apply(form);
        form.addEventListener("change", function (ev) {
          if (ev.target && ev.target.matches && ev.target.matches("[data-kind-select]")) { apply(form); }
        });
      })(forms[i]);
    }
    // A saved place you go often with no location starts with its coordinates folded away; one with a location too.
    var folded = document.querySelectorAll("details.coords");
    for (var j = 0; j < folded.length; j++) { folded[j].open = false; }
  });
})();
