(() => {
  'use strict';
  const section = document.querySelector('#latest-x');
  const anchor = section?.querySelector('a.twitter-timeline');
  if (!anchor) return;

  const root = document.documentElement;
  const theme = () => root.dataset.theme || 'dark';
  let container = anchor.parentElement;
  const template = container.cloneNode(true);
  anchor.dataset.theme = theme();

  new MutationObserver(() => {
    const next = template.cloneNode(true);
    next.querySelector('a').dataset.theme = theme();
    container.replaceWith(next);
    container = next;
    window.twttr?.widgets?.load(container);
  }).observe(root, { attributes: true, attributeFilter: ['data-theme'] });

  function loadWidget() {
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://platform.twitter.com/widgets.js';
    document.head.append(script);
  }

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        observer.disconnect();
        loadWidget();
      }
    }, { rootMargin: '300px' });
    observer.observe(section);
  } else {
    loadWidget();
  }
})();
