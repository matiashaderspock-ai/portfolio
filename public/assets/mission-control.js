(() => {
  'use strict';
  const office = document.querySelector('.office-glass');
  if (!office) return;
  const desks = office.querySelectorAll('.bot-desk');
  desks.forEach(desk => {
    desk.addEventListener('pointerenter', () => desk.classList.remove('job-dismissed'));
    desk.addEventListener('focusin', () => desk.classList.remove('job-dismissed'));
    desk.querySelector('summary').addEventListener('click', () => desk.classList.remove('job-dismissed'));
    desk.addEventListener('toggle', () => {
      if (desk.open) desks.forEach(other => { if (other !== desk) other.open = false; });
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') desks.forEach(desk => { desk.open = false; desk.classList.add('job-dismissed'); });
  });
  const toggle = office.querySelector('.ticker-toggle');
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    const paused = office.classList.toggle('ticker-paused');
    toggle.setAttribute('aria-pressed', String(paused));
    toggle.textContent = paused ? toggle.dataset.resume : toggle.dataset.pause;
  });
})();
