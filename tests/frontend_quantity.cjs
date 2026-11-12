'use strict';
// 真正載入產品腳本驗證十進位運算；不以浮點近似或四捨五入改變貢獻。
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={window:{},document:{addEventListener(){}}};vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/experience_quantity.js','utf8'),context);const q=context.window.QuantityUI;
test('次/小時/公里使用合理間距，部分完成不強制對齊',()=>{
 for(const [unit,step] of [['次','1'],['小時','0.25'],['公里','0.1']])assert.equal(q.profile(unit).step,step);
 assert.equal(q.stepFor('0.5','次'),'any');assert.equal(q.stepFor('1.25','小時'),'0.25');assert.equal(q.stepFor('2.75','公里'),'any');
});
test('小數/六位舊資料不被截斷、重複操作保持精確',()=>{
 assert.equal(q.add('0.000001','1',1),'1.000001');assert.equal(q.add('1.25','0.25',1),'1.5');assert.equal(q.add('2.75','0.1',1),'2.85');
 assert.equal(q.format('1.250000'),'1.25');assert.equal(q.format('0.000001'),'0.000001');assert.equal(q.add('0','1',-1),'0');assert.equal(q.add('1000000000000','1',1),null);
});
