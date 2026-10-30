(() => {
  'use strict';
  const root = document.documentElement;
  const storage = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { /* Optional preference. */ } }
  };
  const language = root.lang;
  // A saved Spanish choice applies to future English-home landings. Explicit
  // switches save before navigation, so returning to English always works.
  if (location.pathname === '/' && storage.get('mh-language') === 'es') {
    location.replace('/es/' + location.search + location.hash);
    return;
  }
  if (document.body.classList.contains('page-home')) storage.set('mh-language', language);
  const languageSwitch = document.querySelector('.language-switch');
  languageSwitch?.addEventListener('click', () => {
    storage.set('mh-language', languageSwitch.hreflang);
    if (location.hash && document.body.classList.contains('page-home')) {
      languageSwitch.hash = location.hash;
    }
  });

  const themeButton = document.querySelector('.theme-toggle');
  const activeTheme = () => root.dataset.theme || 'dark';
  function syncThemeButton() {
    if (!themeButton) return;
    const dark = activeTheme() === 'dark';
    themeButton.setAttribute('aria-label', dark ? themeButton.dataset.lightLabel : themeButton.dataset.darkLabel);
    document.querySelector('meta[name="theme-color"]').content = dark ? '#111f2b' : '#f6f5ef';
  }
  if (themeButton) {
    themeButton.hidden = false;
    syncThemeButton();
    themeButton.addEventListener('click', () => {
      root.dataset.theme = activeTheme() === 'dark' ? 'light' : 'dark';
      storage.set('mh-theme', root.dataset.theme);
      syncThemeButton();
    });
  }

  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const reveals = document.querySelectorAll('.reveal');
  let observer;
  function enableReveals() {
    observer?.disconnect();
    if (motion.matches || !('IntersectionObserver' in window)) {
      reveals.forEach(element => element.classList.remove('reveal-ready'));
      return;
    }
    observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.remove('reveal-ready');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    reveals.forEach(element => {
      // Never hide content already visible, including a direct fragment target.
      if (element.getBoundingClientRect().top > innerHeight) {
        element.classList.add('reveal-ready');
        observer.observe(element);
      }
    });
  }
  enableReveals();
  motion.addEventListener('change', enableReveals);
  // Keyboard focus must reveal a card before its focused link is used.
  document.addEventListener('focusin', event => {
    event.target.closest('.reveal-ready')?.classList.remove('reveal-ready');
  });
  document.querySelectorAll('.print-button').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => window.print());
  });
})();
