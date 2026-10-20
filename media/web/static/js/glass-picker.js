/* Shared asynchronous portal menus. Native form values and change handlers are retained. */
(() => {
  let active = null;
  const cache = new Map(), pending = new Map();
  const node = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text != null) el.textContent = text; return el; };
  function close(restore = false) {
    if (!active) return;
    const prev = active; active = null; prev.menu.remove();
    prev.anchor.setAttribute('aria-expanded', 'false');
    if (restore && prev.anchor.isConnected) prev.anchor.focus({preventScroll:true});
  }
  function position() {
    if (!active) return;
    const {anchor, menu} = active;
    if (!anchor.isConnected) return close();
    const box = anchor.getBoundingClientRect(), height = window.innerHeight, width = window.innerWidth;
    if (box.bottom < 0 || box.top > height) return close();
    const below = height - box.bottom - 12, above = box.top - 12;
    const flip = below < 180 && above > below;
    menu.style.width = Math.min(Math.max(box.width, 260), width - 16) + 'px';
    menu.style.left = Math.max(8, Math.min(box.left, width - menu.offsetWidth - 8)) + 'px';
    menu.style.maxHeight = Math.max(100, Math.min(340, flip ? above : below)) + 'px';
    menu.style.top = flip ? 'auto' : (box.bottom + 5) + 'px';
    menu.style.bottom = flip ? (height - box.top + 5) + 'px' : 'auto';
  }
  function popup(anchor, label) {
    close();
    const menu = node('div', 'fti-picker'); menu.setAttribute('aria-label', label);
    // Keep the portal in the modal's focus scope without putting it under its clipping surfaces.
    menu.setAttribute('role', 'dialog'); menu.tabIndex = -1;
    const list = node('div', 'fti-picker-list'); menu.append(list); document.body.append(menu);
    active = {menu, list, anchor, sequence:0}; anchor.setAttribute('aria-expanded','true'); position(); return active;
  }
  function row(label, action) {
    const item = node('button', 'fti-picker-row', label); item.type='button';
    item.addEventListener('click', action); return item;
  }
  function setValue(input, value) {
    input.value = value;
    input.dispatchEvent(new Event('change', {bubbles:true}));
  }
  async function listing(path, filter, refresh) {
    const key = JSON.stringify([path,filter]), saved = cache.get(key);
    if (!refresh && saved && Date.now() - saved.time < 8000) return saved.html;
    if (pending.has(key)) return pending.get(key);
    const job = (async () => {
      const abort = new AbortController(); const timeout = setTimeout(() => abort.abort(), 15000);
      try {
        const result = await fetch('/dirlist', {method:'POST', credentials:'same-origin', signal:abort.signal,
          headers:{'Content-Type':'application/x-www-form-urlencoded'},
          body:new URLSearchParams({dir:path,filter,show_parent:'true',refresh:refresh?'1':'0'})});
        if (!result.ok) throw new Error('目录读取失败');
        const html = await result.text();
        if (!html.includes('jqueryFileTree')) throw new Error('请重新登录后读取目录');
        cache.delete(key); cache.set(key,{time:Date.now(),html});
        if (cache.size > 128) cache.delete(cache.keys().next().value);
        return html;
      } finally { clearTimeout(timeout); }
    })();
    pending.set(key,job); try { return await job; } finally { pending.delete(key); }
  }
  window.openFileBrowser = function(input, root, filter, folders = true, files = true, closeOnSelect = false) {
    if (active?.anchor === input) return close();
    const state = popup(input,'选择目录或文件');
    state.path = (root || '/').trim() || '/';
    const tools = node('div','fti-picker-toolbar');
    const up = node('button','','上级'), pathLabel = node('span','fti-picker-path'), refresh = node('button','','刷新'), use = node('button','','选定');
    for (const button of [up,refresh,use]) button.type='button';
    tools.append(up,pathLabel,refresh,use); state.menu.prepend(tools);
    use.disabled = !folders;
    async function load(path, fresh = false) {
      const seq = ++state.sequence; state.path=path; pathLabel.textContent=path;
      state.menu.querySelector('.fti-path-search')?.remove();
      state.list.replaceChildren(node('div','fti-picker-status','正在读取目录…（可以继续输入路径）'));
      position();
      try {
        const html = await listing(path, filter || (!files ? 'HIDE_FILES_FILTER' : ''), fresh);
        if (active !== state || state.sequence !== seq) return;
        const doc = new DOMParser().parseFromString(html,'text/html'), fragment = document.createDocumentFragment();
        const error = doc.querySelector('.fti-path-error');
        if (error) { state.list.replaceChildren(node('div','fti-picker-status',error.textContent)); return; }
        const links = [...doc.querySelectorAll('li > a[rel]')];
        const render = (query = '') => {
          const frag = document.createDocumentFragment();
          const matches = links.filter(link => link.textContent.toLowerCase().includes(query));
          for (const link of matches.slice(0,200)) {
            const dir = link.parentElement.classList.contains('directory'), value = link.getAttribute('rel');
            frag.append(row((dir ? '📁 ' : '📄 ') + link.textContent, () => {
              if (dir) { if (folders) setValue(input,value); if (closeOnSelect && folders) close(true); else load(value); }
              else if (files) { setValue(input,value); close(true); }
            }));
          }
          if (matches.length > 200) frag.append(node('div','fti-picker-status','仅显示前 200 项，请输入名称筛选其余项目'));
          if (!matches.length) frag.append(node('div','fti-picker-status','此目录没有匹配的项目'));
          state.list.replaceChildren(frag); position();
        };
        state.menu.querySelector('.fti-path-search')?.remove();
        if (links.length > 30) {
          const search = node('input','form-control fti-picker-search fti-path-search'); search.placeholder='筛选当前目录…';
          search.setAttribute('aria-label','筛选当前目录'); tools.after(search);
          search.addEventListener('input',()=>render(search.value.toLowerCase()));
        }
        render();
      } catch (error) {
        if (active === state && state.sequence === seq) state.list.replaceChildren(node('div','fti-picker-status',error.name === 'AbortError' ? '目录响应超时，可点刷新重试，或直接输入完整路径。' : error.message));
      }
    }
    up.addEventListener('click',()=>load(state.path.replace(/\/+$/,'').replace(/\/[^/]*$/,'/') || '/'));
    refresh.addEventListener('click',()=>load(state.path,true));
    use.addEventListener('click',()=>{setValue(input,state.path);close(true);});
    load(state.path);
  };
  function openSelect(select) {
    if (select.disabled || select.multiple || select.size > 1) return;
    if (active?.anchor === select) return close();
    const state = popup(select,'选择选项'); state.list.setAttribute('role','listbox');
    let search;
    const options = Array.from(select.options);
    function render(query = '') {
      const frag = document.createDocumentFragment();
      for (const option of options.filter(o=>!o.hidden && (!query || o.textContent.toLowerCase().includes(query))).slice(0,200)) {
        const item = row(option.textContent,()=>{select.selectedIndex=option.index;setValue(select,option.value);close(true);});
        item.disabled=option.disabled || option.parentElement.disabled; item.setAttribute('role','option');item.setAttribute('aria-selected',String(option.index === select.selectedIndex));frag.append(item);
      }
      if (!frag.childNodes.length) frag.append(node('div','fti-picker-status','没有匹配的选项'));
      state.list.replaceChildren(frag); position();
    }
    if (options.length > 10) {
      search=node('input','form-control fti-picker-search');search.placeholder='搜索选项…';search.setAttribute('aria-label','搜索选项');state.menu.prepend(search);
      search.addEventListener('input',()=>render(search.value.toLowerCase()));
    }
    render();
    // Bootstrap's modal focus trap must include this portal; disable only while it is open.
    if (search) search.focus({preventScroll:true});
  }
  document.addEventListener('pointerdown', event => {
    const select = event.target.closest('select');
    if (select && !select.multiple && select.size <= 1 && !select.disabled) { event.preventDefault();select.focus({preventScroll:true});openSelect(select);return; }
    if (active && !active.menu.contains(event.target) && event.target !== active.anchor) close();
  },true);
  document.addEventListener('keydown',event=>{
    if (event.key === 'Escape' && active) {event.preventDefault();event.stopImmediatePropagation();close(true);return;}
    if (!active && event.target.matches('select:not([multiple])') && ['Enter',' ','ArrowDown','ArrowUp'].includes(event.key)) {event.preventDefault();openSelect(event.target);return;}
    if (!active) return;
    if (event.key === 'Tab') return close();
    if (event.target === active.anchor && ['Enter',' '].includes(event.key) && event.target.tagName === 'SELECT') {event.preventDefault();active.list.querySelector('[aria-selected="true"]')?.click();return;}
    if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
      const rows = [...active.list.querySelectorAll('button:not(:disabled)')];if (!rows.length) return;
      event.preventDefault(); let i=rows.indexOf(document.activeElement);
      i=event.key==='Home'?0:event.key==='End'?rows.length-1:(i+(event.key==='ArrowDown'?1:-1)+rows.length)%rows.length;
      rows[i].focus({preventScroll:true});rows[i].scrollIntoView({block:'nearest'});
    }
  },true);
  // Bootstrap focusin containment normally returns focus from body portals to the modal.
  document.addEventListener('focusin',event=>{if(active?.menu.contains(event.target))event.stopImmediatePropagation();},true);
  document.addEventListener('input',event=>{if(active?.anchor===event.target && event.target.tagName==='INPUT')close();});
  document.addEventListener('hidden.bs.modal',()=>close());
  if (window.jQuery) jQuery(document).on('hide.bs.modal',()=>close());
  window.addEventListener('resize',position);document.addEventListener('scroll',event=>{if(active && !active.menu.contains(event.target)) position();},true);
  window.addEventListener('popstate',()=>close());
})();
