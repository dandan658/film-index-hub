/* Animate completed page navigation only; preserve all original event handlers. */
(() => {
  const start = () => {
    const host = document.getElementById('page_content');
    if (!host || !window.jQuery || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    jQuery(document).ajaxComplete((_event, xhr, settings) => {
      const url = new URL(settings.url, location.href);
      if (url.origin !== location.origin || !/^\/(mediafile|unidentification|history|tmdbcache|service|basic|users|library|directorysync|notification|filterrule|customwords|indexer|downloader|mediaserver|subtitle|douban)$/.test(url.pathname) || xhr.status !== 200) return;
      host.classList.remove('fti-page-enter');
      requestAnimationFrame(() => requestAnimationFrame(() => host.classList.add('fti-page-enter')));
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true}); else start();
})();
