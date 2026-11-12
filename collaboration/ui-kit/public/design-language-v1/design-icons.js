/* 功能圖示採固定白名單 SVG；不把呼叫端字串插入 SVG 標記。 */
window.DesignIcons = (() => {
  const paths={
    world:'<path d="m3 10 9-7 9 7v10H3Z"/><path d="M9 20v-7h6v7"/>',
    goals:'<path d="M12 21V10M12 14C3 14 3 7 3 5c8 0 9 5 9 9Zm0-4c0-7 6-8 9-8 0 7-5 10-9 10"/>',
    history:'<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    people:'<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m2-16a3 3 0 0 1 0 6m1 4a5 5 0 0 1 3 5"/>',
    back:'<path d="m14 5-7 7 7 7"/>',close:'<path d="m6 6 12 12M18 6 6 18"/>',
    settings:'<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 3 2 2-1 3 2 3 3-1 3 3 3-1 1-3 3-1 2-3-2-2 1-3-2-3-3 1-3-3Z"/>',
    retry:'<path d="M20 11a8 8 0 1 0-2 7M20 4v7h-7"/>',check:'<path d="m4 12 5 5L20 6"/>',
    warning:'<path d="m12 3 10 18H2Z"/><path d="M12 9v5m0 3v.1"/>',
    search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
    plus:'<path d="M12 4v16M4 12h16"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
    sound:'<path d="m3 9 5 0 5-4v14l-5-4H3Zm14-1a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
    music:'<path d="M9 17V5l11-2v12M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',
    sprout:'<path d="M12 22V11M12 14C3 14 3 5 3 3c9 0 9 8 9 11Zm0-3c0-9 9-10 10-10 0 9-7 12-10 12"/>'
  };
  function render(name) {const drawing=Object.hasOwn(paths,name)?paths[name]:paths.sprout;return `<svg class="lw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${drawing}</svg>`;}
  return {render};
})();
