/* 裝置判斷只調整說明，不能用作登入、權限或安裝成功的判據。 */
window.LifeWorldInstallGuide=Object.freeze({route:({userAgent='',maxTouchPoints=0,standalone=false,promptAvailable=false}={})=>{
  if(standalone)return 'installed';
  if(/Instagram|FBAN|FBAV|FBIOS|FB_IAB|MessengerForiOS|\bLine\//i.test(userAgent))return 'inapp';
  if(/iPhone|iPad|iPod/i.test(userAgent)||(/Macintosh/i.test(userAgent)&&maxTouchPoints>1))return 'ios';
  if(promptAvailable)return 'prompt';
  if(/Android/i.test(userAgent))return 'android';
  return 'generic';
}});
