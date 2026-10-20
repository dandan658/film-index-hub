(() => {
 const applyTheme=dark=>{document.documentElement.style.background='transparent';document.documentElement.style.colorScheme=dark?'dark':'light';document.body.classList.toggle('theme-dark',dark);document.body.classList.toggle('theme-light',!dark)};
 applyTheme(false);
 const allowed=new Set(['mediafile','unidentification','history','tmdbcache','service','basic','library','directorysync','notification','customwords','mediaserver','subtitle']);
 window.addEventListener('message',e=>{
  if(e.origin!==location.origin||e.source!==parent)return;
  if(e.data?.type==='film-hub:theme'&&typeof e.data.dark==='boolean'){applyTheme(false);return}
  if(e.data?.type==='film-hub:navigate'&&allowed.has(e.data.page)&&typeof navmenu==='function')navmenu(e.data.page);
 });
})();

