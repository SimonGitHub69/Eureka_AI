/**
 * Compat: stampa Registro IVA caricava print-date-it.js.
 * La logica vive in date-it.js (EurekaDateIT / EurekaPrintDateIT).
 */
(function () {
  if (window.EurekaDateIT && !window.EurekaPrintDateIT) {
    window.EurekaPrintDateIT = window.EurekaDateIT;
  }
})();
