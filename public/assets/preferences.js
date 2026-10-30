/* Apply the saved theme before paint. Storage can be unavailable in private mode. */
(() => {
  let theme = 'dark';
  try {
    const saved = localStorage.getItem('mh-theme');
    if (saved === 'light' || saved === 'dark') theme = saved;
  } catch { /* Dark remains the default. */ }
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#111f2b' : '#f6f5ef';
})();
