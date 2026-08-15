const tasks = [
  { id: 1, task_uid: 'SESS-A', title: '航空支架出图', part_name: 'bracket_v3', material: '铝 6061', status: 'success', created_at: '2026-08-16 10:00' },
  { id: 2, task_uid: 'SESS-B', title: null, part_name: 'flange_01', material: null, status: 'archived', created_at: '2026-08-15 12:30' },
  { id: 3, task_uid: null, title: '空任务', part_name: null, material: null, status: null, created_at: '' },
];
const files = [
  { task_id: 1 }, { task_id: 1 }, { task_id: 1 },
  { task_id: 2 },
];
const delay = async (x) => x;
const mockProjects = [{ id: 'MOCK', name: 'mock', enabled: true, desc: '', drawings: 0, members: 0, updatedAt: '' }];

async function list() {
  if (!Array.isArray(tasks) || tasks.length === 0) return delay(mockProjects);
  const fileCount = new Map();
  for (const f of files || []) {
    const k = f.task_id || 0;
    fileCount.set(k, (fileCount.get(k) || 0) + 1);
  }
  return tasks.map((t) => {
    const st = (t.status || '').toLowerCase();
    const enabled = !(st === 'archived' || st === 'disabled');
    const partName = t.part_name || t.title || `任务 #${t.id}`;
    const material = t.material || '未指定材料';
    return {
      id: t.task_uid || `TASK-${t.id}`,
      name: t.title || partName,
      enabled,
      desc: `${partName}｜${material}｜状态：${t.status || 'unknown'}`,
      drawings: fileCount.get(t.id) || 0,
      members: 1,
      updatedAt: t.created_at || '',
    };
  });
}

const cards = await list();
console.log('cards:', JSON.stringify(cards, null, 2));
const [c1, c2, c3] = cards;
const asserts = [
  ['c1.id=SESS-A', c1.id === 'SESS-A'],
  ['c1.enabled(success->true)', c1.enabled === true],
  ['c1.drawings=3', c1.drawings === 3],
  ['c2.enabled(archived->false)', c2.enabled === false],
  ['c2.name回退part_name', c2.name === 'flange_01'],
  ['c2.material兜底', c2.desc.includes('未指定材料')],
  ['c3.id走TASK-兜底', c3.id === 'TASK-3'],
  ['c3.drawings=0', c3.drawings === 0],
];
let allOk = true;
for (const [n, r] of asserts) {
  console.log((r ? '  OK   ' : '  FAIL ') + n);
  if (!r) allOk = false;
}
console.log(allOk ? 'ALL PASS' : 'FAIL');
process.exit(allOk ? 0 : 1);