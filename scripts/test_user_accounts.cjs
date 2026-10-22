const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const ts = require(process.env.TYPESCRIPT_PATH || '../frontend/node_modules/typescript');
const source = fs.readFileSync(process.env.USER_STORE_PATH || path.join(__dirname, '../frontend/src/stores/users.ts'), 'utf8');
const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
function setup(api) {
 const output = {};
 vm.runInNewContext(js, {exports: output, console, require(name) {
  if(name === 'pinia') return {defineStore: (_, fn) => fn};
  if(name === 'vue') return {ref: value => ({value}), computed: fn => ({get value(){return fn()}})};
  if(name === '@/services') return {apiService: api};
  if(name === '@/utils/helpers') return {getErrorMessage: error => error.message};
  throw new Error(name);
 }});
 const store=output.useUserStore();
 store.users.value=[{username:'first',is_current:true},{username:'second',is_current:false}];
 store.currentUser.value='first';
 return store;
}
(async()=>{
 let releaseOld, releaseSwitch, calls=0;
 const api={
  getUserQuota: async()=>{calls++; if(calls===1)return new Promise(resolve=>{releaseOld=resolve}); return {success:true,quota:{total:200,used:20,total_gb:2,used_gb:.2}}},
  switchUser: async()=>new Promise(resolve=>{releaseSwitch=resolve}),
  checkUser: async()=>({success:true,valid:false,message:'expired'})
 };
 const store=setup(api);
 const oldRequest=store.fetchUserQuota();
 const switching=store.switchUser('second');
 assert.equal(store.switching.value,true);
 assert.equal(await store.switchUser('first'),false);
 releaseSwitch({success:true,current_user:{quota:{total:200,used:20}}}); await switching;
 assert.equal(store.currentUser.value,'second'); assert.equal(store.switching.value,false);
 assert.equal(store.users.value[1].is_current,true); assert.equal(store.userQuota.value.total,200);
 releaseOld({success:true,quota:{total:999,used:999}}); await oldRequest;
 assert.equal(store.userQuota.value.total,200,'late old-account quota must not replace active account');
 await store.checkUser('second');
 assert.equal(store.users.value[1].cookies_valid,false); assert.equal(store.users.value[1].quota,undefined);
 assert.equal(store.userStats.value.invalid,1); assert.equal(store.userStats.value.valid,0); assert.equal(store.userStats.value.unchecked,1);
 const failure=setup({switchUser:async()=>({success:false,message:'failed'})});
 await assert.rejects(failure.switchUser('second'));
 assert.equal(failure.currentUser.value,'first'); assert.equal(failure.users.value[0].is_current,true); assert.equal(failure.switching.value,false);
 const unknown=setup({checkUser:async()=>({success:true,valid:null,message:'network'})});
 await unknown.checkUser('second'); assert.equal(unknown.users.value[1].cookies_valid,null); assert.equal(unknown.userStats.value.invalid,0);
 console.log('PASS account switching, duplicate submission, late quota isolation, probe states and failure preservation');
})().catch(error=>{console.error(error);process.exitCode=1});
