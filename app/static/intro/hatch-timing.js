/* 獨立導覽的可審節奏；第三擊先保留深裂蛋，再開殼，避免直接跳成角色。 */
window.LifeWorldHatchTiming=Object.freeze({
  fine:800,deep:1000,reduced:80,done:4800,
  reveal:Object.freeze([
    {at:0,key:'anticipate',label:'先停一下，蛋裡有了小小的動靜。'},
    {at:650,key:'shell',label:'蛋殼正慢慢打開。'},
    {at:1650,key:'peek',label:'Lumi 慢慢探出頭。'},
    {at:2550,key:'closed',label:'Lumi 正在適應這個世界。'},
    {at:3250,key:'open',label:'Lumi 慢慢睜開眼睛。'},
    {at:4200,key:'settled',label:'你好，我是 Lumi。'}
  ])
});
