/* 從本檔位置推導靜態根目錄，主站與可攜式 Main Web 包共用來源。 */
window.LifeWorldStaticBase = new URL('../', document.currentScript.src).pathname.replace(/\/$/,'');
