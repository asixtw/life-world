/* Lumi 只呈現姿勢，不讀寫帳號、孵化、進度或獎勵。 */
window.LumiUI = (() => {
  'use strict';
  const poses = new Set(['idle','welcome','listening','confirmed','celebrate','quiet','curious','surprised','thinking','running','sleeping','side','back','three-quarter','hatch-peek','hatch-closed']);
  const sizes = {small:80, medium:256, hero:360};
  const escape = value => String(value).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  /** 輸入姿勢／尺寸／動效／替代文字，回傳安全 HTML；無資料或播放副作用。 */
  function render({pose='idle', size='hero', motion=true, alt='Lumi 溫暖地陪伴你'} = {}) {
    pose = poses.has(pose) ? pose : 'idle'; size = Object.hasOwn(sizes,size) ? size : 'hero';
    const sourceSize=size==='small'?256:512, base=(window.LifeWorldStaticBase||'/static')+'/art/design-v1/lumi-'+pose;
    return `<div class="hero-art lumi-art lw-lumi" data-lumi-pose="${pose}" data-lumi-size="${size}" data-motion="${motion===true}" style="--lumi-size:${sizes[size]}px"><img class="lumi-asset" data-lumi-art src="${base}-${sourceSize}.png" srcset="${base}-256.png 256w, ${base}-512.png 512w, ${base}-1024.png 1024w" sizes="${sizes[size]}px" width="512" height="512" alt="${escape(alt)}"><div data-lumi-fallback hidden><div class="ground"></div><div class="lumi"><i class="leaf"></i><i class="eyes"></i><i class="beak"></i><i class="wing"></i></div><span class="lumi-fallback-label">Lumi 在這裡陪伴你</span></div></div>`;
  }
  return {render};
})();
