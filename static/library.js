(function(){
let data=null,q='',probs=false,css=false;
const el=(t,o={},...k)=>{const e=document.createElement(t);for(const[a,v]of Object.entries(o)){if(a==='class')e.className=v;else if(a==='text')e.textContent=v;else if(a.startsWith('on'))e[a]=v;else e.setAttribute(a,v)}
 k.forEach(c=>c!=null&&e.append(c));return e};
const n=x=>Number(x).toLocaleString();
function style(){if(css)return;css=true;document.head.append(el('style',{text:
'.lib-sum{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:10px}.lib-sum b{display:block;font-size:20px}.lib-sum span{font-size:12px;color:var(--mut)}'+
'.lib-ban{border:1px solid var(--warn);color:var(--warn);border-radius:8px;padding:8px 10px;margin-bottom:10px}'+
'.lib-err{color:var(--err);font-weight:600}.lib-link{cursor:pointer;text-decoration:underline;background:none;border:0;padding:0;font:inherit}'+
'.lib-det td{background:var(--bg);font-size:13px;word-break:break-all}.lib-det div{padding:1px 0}'+
'#libtbl td.num,#libtbl th.num{text-align:right;white-space:nowrap}'})) }

async function toggle(r,tr){
 const nx=tr.nextSibling;if(nx&&nx.className==='lib-det'){nx.remove();return}
 const td=el('td',{colspan:7,text:'Loading…'}),d=el('tr',{class:'lib-det'},td);tr.after(d);
 try{const j=await api('/api/library/missing?folder='+encodeURIComponent(r.folder));td.textContent='';
  const sec=(h,a)=>{if(!a.length)return;td.append(el('div',{class:'mut',text:h}));a.forEach(f=>td.append(el('div',{text:f})))};
  sec('Downloaded, not on the NAS yet:',j.files);
  if(j.truncated)td.append(el('div',{class:'mut',text:'(list truncated to 500)'}));
  if(!td.childNodes.length)td.textContent='Nothing to show.'}catch{d.remove()}
}

function render(root){
 root.textContent='';const t=data.totals;
 const sum=el('div',{class:'lib-sum'});
 [['Tracks in library (NAS)',t.nas],['Playlists',t.playlists],['Waiting to copy',t.missing_on_nas],['Differ from archive',t.differs]].forEach(([l,v])=>
  sum.append(el('div',{},el('b',{text:n(v),class:l==='Waiting to copy'&&v>0?'errors':''}),el('span',{text:l}))));
 const card=el('div',{class:'card'},sum);
 if(!data.nas_mounted)card.append(el('div',{class:'lib-ban',text:'NAS is not mounted: NAS counts are unavailable and sync is disabled.'}));
 if(t.garbled_folders)card.append(el('div',{class:'lib-ban',text:t.garbled_folders+' NAS folder name(s) are garbled (UTF-8 read as Latin-1). These are legacy leftovers; the repaired name is shown in the table.'}));
 card.append(el('div',{class:'mut',style:'margin-bottom:8px',text:'The NAS count can be higher than the archive when older or hand-added files sit in the folder, and lower when tracks were deleted or renamed. The archive stores video IDs, not file names, so the two cannot be compared file by file.'}));
 const btn=el('button',{class:'pri',text:'Sync waiting files to NAS',onclick:async()=>{
  if(!confirm('Copy '+t.missing_on_nas+' waiting file(s) to the NAS now?'))return;
  try{await api('/api/library/sync','POST');show('run')}catch{}}});
 btn.disabled=!data.nas_mounted||!t.missing_on_nas;
 const search=el('input',{type:'text',class:'grow',placeholder:'Filter folders',value:q});
 const pc=el('input',{type:'checkbox'});pc.checked=probs;
 const rf=el('button',{text:'Refresh',onclick:()=>load(root)});
 card.append(el('div',{class:'row'},btn,rf,el('span',{class:'mut',text:'Progress is shown in the Run tab.'})));
 root.append(card);
 const tb=el('tbody');
 const fill=()=>{tb.textContent='';const s=q.toLowerCase();
  data.folders.filter(r=>(!probs||r.garbled||r.missing_on_nas>0||r.differs)&&(!s||r.folder.toLowerCase().includes(s)||(r.fixed_name||'').toLowerCase().includes(s))).forEach(r=>{
   const pl=r.single?'single videos (no playlist)':(r.playlist_name==null?'— not in your list':r.playlist_name);
   const d=r.diff,dtxt=d==null?'—':(d===0?'same':(d>0?'+'+n(d)+' on NAS':n(-d)+' fewer on NAS'));
   const tr=el('tr',{},
    el('td',{text:r.folder}),
    el('td',{},pl,r.enabled===false?el('span',{class:'pill',text:'not selected',style:'margin-left:6px'}):null),
    el('td',{class:'num'},el('b',{text:n(r.nas)})),
    el('td',{class:'num hm',text:r.archive==null?'—':n(r.archive)}),
    el('td',{class:'num hm',text:dtxt,style:r.differs?'color:var(--warn);font-weight:600':'color:var(--mut)',title:r.differs?'Archive and NAS counts differ noticeably':''}),
    el('td',{class:'num'},r.missing_on_nas>0?el('button',{class:'lib-link lib-err',text:n(r.missing_on_nas),onclick:()=>toggle(r,tr)}):'—'),
    el('td',{class:'hm'},r.garbled?el('span',{class:'stopped',text:'garbled → '+r.fixed_name}):null));
   tb.append(tr)});
  if(!tb.childNodes.length)tb.append(el('tr',{},el('td',{colspan:7,class:'mut',text:'No folders.'})))};
 search.oninput=()=>{q=search.value;fill()};
 pc.onchange=()=>{probs=pc.checked;fill()};
 root.append(el('div',{class:'card'},el('div',{class:'row',style:'margin-bottom:8px'},search,el('label',{class:'mut'},pc,' problems only'))));
 const th=(x,c='')=>el('th',{class:c,text:x});
 root.lastChild.append(el('div',{class:'tablewrap'},el('table',{id:'libtbl'},el('thead',{},el('tr',{},
  th('Folder'),th('Playlist'),th('Tracks on NAS','num'),th('Archive','num hm'),th('NAS vs archive','num hm'),th('Waiting to copy','num'),th('Note','hm'))),tb)));
 fill();
}

async function load(root){try{data=await api('/api/library');render(root)}catch{}}
window.initLibrary=function(root){style();load(root)};
})();
