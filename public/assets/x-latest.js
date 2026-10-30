(() => {
  'use strict';
  const strip = document.querySelector('#x-cards');
  if (!strip) return;
  const es = document.documentElement.lang === 'es';
  const status = document.querySelector('#x-status');
  const labels = es ? {post: 'Publicación', quote: 'Cita', repost: 'Republicación'} : {post: 'Post', quote: 'Quote', repost: 'Repost'};
  const samples = [...strip.children].map(card => card.cloneNode(true));
  const allowedLink = value => typeof value === 'string' && /^https:\/\/x\.com\/(?:pandasczos|i)\/status\/\d{1,19}$/.test(value);
  const valid = post => post && typeof post.text === 'string' && post.text.trim() && Object.hasOwn(labels, post.type) && allowedLink(post.link) && /^\d{4}-\d{2}-\d{2}$/.test(post.created_date) && Number.isFinite(Date.parse(post.created_date));
  fetch('/data/x-latest.json', {cache: 'no-cache'})
    .then(response => { if (!response.ok) throw new Error('Feed unavailable'); return response.json(); })
    .then(feed => {
      if (feed.sample !== false || !Array.isArray(feed.posts)) return;
      const posts = feed.posts.filter(valid).slice(0, 5);
      if (!posts.length) return;
      const cards = posts.map(post => {
        const card = document.createElement('article'); card.className = 'x-card';
        const kind = document.createElement('p'); kind.className = 'x-kind'; kind.textContent = labels[post.type];
        const date = document.createElement('time'); date.dateTime = post.created_date;
        date.textContent = new Intl.DateTimeFormat(es ? 'es-BO' : 'en-US', {dateStyle: 'medium', timeZone: 'UTC'}).format(new Date(post.created_date + 'T00:00:00Z'));
        const heading = document.createElement('h3'); heading.textContent = '@pandasczos';
        const text = document.createElement('p'); text.className = 'x-text'; text.textContent = post.text;
        card.append(kind, date, heading, text);
        if (typeof post.thumbnail === 'string' && /^https:\/\/pbs\.twimg\.com\/(?:media|ext_tw_video_thumb|amplify_video_thumb|tweet_video_thumb)\//.test(post.thumbnail)) {
          const img = document.createElement('img'); img.src = post.thumbnail; img.alt = es ? 'Miniatura de la publicación en X' : 'Thumbnail from the X post'; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
          img.addEventListener('error', () => img.remove(), {once: true}); card.append(img);
        }
        const link = document.createElement('a'); link.className = 'text-link'; link.href = post.link;
        link.textContent = es ? 'Ver publicación ↗' : 'View post ↗';
        link.setAttribute('aria-label', (es ? 'Ver publicación del ' : 'View post dated ') + date.textContent + ' — ' + labels[post.type]);
        card.append(link); return card;
      });
      while (cards.length < 5) cards.push(samples[cards.length]);
      strip.replaceChildren(...cards);
      status.textContent = posts.length === 5 ? (es ? 'Publicaciones públicas · fechas originales.' : 'Public posts · original dates shown.') : (es ? `${posts.length} publicaciones públicas; las demás tarjetas son ejemplos.` : `${posts.length} public posts; remaining cards are samples.`);
    })
    .catch(() => { /* The localized, clearly marked static sample cards remain. */ });
})();
