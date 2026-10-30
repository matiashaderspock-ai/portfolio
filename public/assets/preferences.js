/* Apply the saved theme before paint. Storage can be unavailable in private mode. */
(() => {
  try {
    const theme = localStorage.getItem('mh-theme');
    if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
  } catch { /* The system preference remains the default. */ }
})();
