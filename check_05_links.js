const fs = require('fs');
const path = require('path');

const html = fs.readFileSync('05-학생산출물/index.html', 'utf8');
const scriptMatch = html.match(/const OUTPUTS = \[([\s\S]*?)\];\s*const outputGrid/);
if (scriptMatch) {
  const code = 'const OUTPUTS = [' + scriptMatch[1] + ']; return OUTPUTS;';
  const outputs = new Function(code)();
  
  console.log(`Checking ${outputs.length} subjects in 05-학생산출물...`);
  outputs.forEach(subj => {
    console.log(`\n=== [${subj.id}] ${subj.title} ===`);
    subj.pillars.forEach(p => {
      p.items.forEach(item => {
        const fullPath = path.join('05-학생산출물', item.url);
        const exists = fs.existsSync(fullPath);
        if (!exists) {
          console.log(`  ❌ MISSING: ${item.name} -> "${item.url}"`);
        } else {
          console.log(`  ✅ EXISTS: ${item.name} (${item.type})`);
        }
      });
    });
  });
}
