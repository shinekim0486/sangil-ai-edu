const teams=[
  {id:'A',name:'박스형 케이스',file:'A팀_박스형_케이스도면.pdf',thumb:'A팀_박스형_케이스도면_thumb.png',desc:'직선형 외곽과 R5 모서리를 적용한 기본 박스 구조'},
  {id:'B',name:'쐐기형 케이스',file:'B팀_쐐기형_케이스도면.pdf',thumb:'B팀_쐐기형_케이스도면_thumb.png',desc:'전면 높이 변화를 적용한 경사형 차체 구조'},
  {id:'C',name:'픽업형 케이스',file:'C팀_픽업형_케이스도면.pdf',thumb:'C팀_픽업형_케이스도면_thumb.png',desc:'전후 공간을 구분한 픽업 스타일 차체 구조'},
  {id:'D',name:'버스형 케이스',file:'D팀_버스형_케이스도면.pdf',thumb:'D팀_버스형_케이스도면_thumb.png',desc:'높은 상부 공간과 R8 모서리를 적용한 구조'},
  {id:'E',name:'스포츠형 케이스',file:'E팀_스포츠형_케이스도면.pdf',thumb:'E팀_스포츠형_케이스도면_thumb.png',desc:'낮은 전고와 R15 곡률을 살린 스포츠형 구조'},
  {id:'F',name:'곡면형 케이스',file:'F팀_곡면형_케이스도면.pdf',thumb:'F팀_곡면형_케이스도면_thumb.png',desc:'R20 곡률을 중심으로 구성한 부드러운 외곽 구조'}
];
const students=[
['30102','A','배터리 홀더','하','미','하','하','하','하','same',1],['30103','A','초음파 센서 브래킷','중','중','중','상','중','상','up',0],['30104','A','모터 브래킷','중','상','중','중','중','중','same',0],['30105','A','라즈베리파이 받침','하','하','중','중','하','중','up',0],['30106','A','차체 덮개','중','중','상','상','중','상','up',0],
['30107','B','카메라 장착부','상','상','중','상','상','상','same',0],['30108','B','배터리 홀더','미','하','하','하','미','하','up',1],['30110','B','모터 브래킷','하','중','중','중','하','중','up',0],['30111','B','라즈베리파이 받침','중','상','상','상','중','상','up',0],['30112','B','차체 덮개','하','하','미','하','하','하','same',1],
['30201','C','카메라 장착부','중','중','중','상','중','상','up',0],['30202','C','배터리 홀더','상','상','상','상','상','상','same',0],['30203','C','초음파 센서 브래킷','하','하','하','하','하','하','same',1],['30204','C','모터 브래킷','중','중','중','중','중','중','same',0],['30205','C','라즈베리파이 받침','하','중','중','중','하','중','up',0],['30206','C','차체 덮개','중','중','상','상','중','상','up',0],
['30208','D','배터리 홀더','중','중','중','중','중','중','same',0],['30209','D','초음파 센서 브래킷','상','상','상','중','상','중','down',0],['30210','D','모터 브래킷','하','하','하','미','하','미','down',1],['30211','D','라즈베리파이 받침','중','중','중','상','중','상','up',0],['30212','D','차체 덮개','중','중','중','중','중','중','same',0],
['30301','E','카메라 장착부','상','상','상','상','상','상','same',0],['30302','E','배터리 홀더','중','중','중','중','중','중','same',0],['30303','E','초음파 센서 브래킷','하','하','하','하','하','하','same',1],['30304','E','모터 브래킷','중','하','중','상','중','상','up',0],['30305','E','라즈베리파이 받침','하','중','중','중','하','중','up',0],['30306','E','차체 덮개','중','중','상','상','중','상','up',0],
['30307','F','카메라 장착부','하','미','하','하','하','하','same',1],['30308','F','배터리 홀더','상','상','상','상','상','상','same',0],['30309','F','초음파 센서 브래킷','중','중','중','중','중','중','same',0],['30310','F','모터 브래킷','하','하','중','중','하','중','up',0],['30311','F','라즈베리파이 받침','중','상','중','상','중','상','up',0],['30312','F','차체 덮개','중','중','중','상','중','상','up',0]
].map(([id,team,part,s1,s2,s3,s4,pre,post,trend,support])=>({id,team,part,scores:[s1,s2,s3,s4],pre,post,trend,support:Boolean(support)}));

const asset=p=>`assets/${encodeURIComponent(p)}`;
const teamCounts=Object.fromEntries(teams.map(t=>[t.id,students.filter(s=>s.team===t.id).length]));
document.querySelector('#teamGrid').innerHTML=teams.map(t=>`<a class="team-card" href="${asset(t.file)}" target="_blank"><img src="${asset(t.thumb)}" alt="${t.name} 도면"><div class="team-card-body"><div class="team-meta"><span class="team-badge">${t.id}</span><span class="team-count">${teamCounts[t.id]}명 · PDF 1쪽</span></div><h3>${t.name}</h3><p>${t.desc}</p></div></a>`).join('');

const cls=v=>v==='상'?'high':v==='중'?'mid':v==='하'?'low':'missing';
const trendLabel={up:'향상 ▲',same:'유지 =',down:'하락 ▼'};
function renderStudents(){
 const q=document.querySelector('#searchInput').value.trim().toLowerCase();
 const team=document.querySelector('#teamFilter').value;
 const trend=document.querySelector('#trendFilter').value;
 const support=document.querySelector('#supportFilter').checked;
 const list=students.filter(s=>(!q||s.id.includes(q)||s.part.toLowerCase().includes(q))&&(!team||s.team===team)&&(!trend||s.trend===trend)&&(!support||s.support));
 document.querySelector('#resultCount').textContent=`전체 33명 중 ${list.length}명 표시`;
 document.querySelector('#studentGrid').innerHTML=list.length?list.map(s=>`<article class="student-card"><div class="student-top"><span class="student-id">${s.id}</span><span class="student-team">${s.team}팀</span></div><h3>${s.part}</h3><div class="scores">${s.scores.map((v,i)=>`<span class="score ${cls(v)}">${i+1}차시<b>${v}</b></span>`).join('')}</div><div class="trend"><span>사전 <strong>${s.pre}</strong> → 사후 <strong>${s.post}</strong></span><strong class="${s.trend}">${trendLabel[s.trend]}</strong></div>${s.support?'<span class="support">보충지도 대상</span>':''}</article>`).join(''):'<div class="empty">조건에 맞는 학생 기록이 없습니다.</div>';
}
['searchInput','teamFilter','trendFilter','supportFilter'].forEach(id=>document.querySelector(`#${id}`).addEventListener(id==='searchInput'?'input':'change',renderStudents));
renderStudents();
