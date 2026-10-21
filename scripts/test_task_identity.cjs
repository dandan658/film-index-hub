const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require(process.env.TYPESCRIPT_PATH || '../frontend/node_modules/typescript');
let request;
const api = {
  executeTask: async (index, uid) => { request = { index, uid }; return { success: true, task_uid: uid }; },
  executeBatchTasks: async (ids, uids) => { request = { ids, uids }; return { success: true }; }
};
const exportsObject = {};
const source = fs.readFileSync(process.env.TASK_STORE_PATH || require('node:path').join(__dirname, '../frontend/src/stores/tasks.ts'), 'utf8');
const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
vm.runInNewContext(js, {exports: exportsObject, require(name) {
  if (name === 'pinia') return { defineStore: (_, setup) => setup };
  if (name === 'vue') return { ref: value => ({value}), computed: fn => ({get value() {return fn()}}) };
  if (name === '@/services') return {apiService: api};
  if (name === '@/utils/constants') return {TASK_STATUS: {RUNNING: 'running', ERROR: 'error'}};
  if (name === '@/utils/helpers') return {getErrorMessage: e => e.message};
  throw new Error(name);
}, console});
(async () => {
 const store = exportsObject.useTaskStore();
 store.tasks.value = ['牧神记','沧元图','大主宰','光阴之外','择日飞升'].map((name, i) => ({name, order:i+1, task_uid:`uid-${i}`, status:'normal'}));
 await store.executeTask(3);
 assert.equal(request.uid, 'uid-3');
 assert.equal(store.tasks.value[3].status, 'running');
 assert.equal(store.tasks.value[2].status, 'normal');
 assert.equal(store.tasks.value[4].status, 'normal');
 assert.equal(new Set(store.tasks.value.map(t => t.task_uid)).size, 5);
 await store.executeBatchTasks([0,4]);
 assert.equal(request.uids.join(','), 'uid-0,uid-4');
 assert.equal(store.tasks.value[4].status, 'running');
 assert.equal(store.tasks.value[1].status, 'normal');
 store.tasks.value[0].order=5; store.tasks.value[4].order=1;
 await store.executeBatchTasks([0], ['uid-0']);
 assert.equal(request.uids.join(','), 'uid-0');
 console.log('PASS selected task, adjacent rows, immutable identities and batch execution');
})().catch(error => {console.error(error); process.exitCode=1});
