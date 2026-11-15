"use strict";
const $=id=>document.getElementById(id);
const rad=d=>d*Math.PI/180;
const TAU=Math.PI*2;
const state={body:"moon",mode:"dual",orbit:false,sites:[],reference:null,candidates:[],site:null,earth:null,evidence:null,filter:"all",requestToken:0,evidenceToken:0,snapshotToken:0,angles:{target:-0.5,earth:-0.3},pitches:{target:0.18,earth:0.18},zooms:{target:1,earth:1}};
const globes={target:{canvas:$("target-globe"),texture:"moon",markers:[],hits:[],drag:null},earth:{canvas:$("earth-globe"),texture:"earth",markers:[],hits:[],drag:null}};
const textures={};
const sources={moon:"https://www.solarsystemscope.com/textures/download/2k_moon.jpg",mars:"https://www.solarsystemscope.com/textures/download/2k_mars.jpg",earth:"https://www.solarsystemscope.com/textures/download/2k_earth_daymap.jpg"};
for(const [body,url] of Object.entries(sources)){
 const img=new Image();textures[body]=img;
 img.onload=()=>{img.ready=true;paintBoth()};
 img.onerror=()=>{img.ready=false;paintBoth()};
 img.src=url;
}
async function json(path){const response=await fetch(path,{headers:{"Accept":"application/json"}});if(!response.ok)throw new Error("HTTP "+response.status);return response.json();}
function str(v){return v==null?"—":String(v)}
function deg(v){return Number(v).toFixed(3)+"°"}
function coords(obj){return obj?deg(obj.latitude)+", "+deg(obj.longitude):"Coordinates unavailable"}
function setText(id,text){const node=$(id);if(node)node.textContent=text}
function openData(){
 const panel=$("telemetry");panel.hidden=false;
 $("show-data").setAttribute("aria-expanded","true");
 $("show-data").textContent="◫ DATA OPEN";
}
function closeData(){
 const panel=$("telemetry");panel.hidden=true;
 $("show-data").setAttribute("aria-expanded","false");
 $("show-data").textContent="◫ VIEW DATA";
 $("show-data").focus();
}

function currentIndex(body){return state.sites.findIndex(s=>s.id===body)}
function setMode(mode){
 state.mode=mode;
 const grid=$("stages");
 grid.classList.toggle("only-target",mode==="target");
 grid.classList.toggle("only-earth",mode==="earth");
 for(const kind of ["dual","target","earth"]){
  const button=$("mode-"+kind);
  button.classList.toggle("active",mode===kind);
  button.setAttribute("aria-pressed",String(mode===kind));
 }
 requestAnimationFrame(paintBoth);
}
function setBody(body){
 state.body=body;globes.target.texture=body;
 for(const kind of ["moon","mars"]){
  const node=$("target-"+kind);node.classList.toggle("active",kind===body);
  node.setAttribute("aria-pressed",String(kind===body));
 }
 setText("target-title",body==="moon"?"Moon · NASA LRO LOLA":"Mars · NASA MGS MOLA");
 loadSites(body);
}
function globeProject(lat,lon,kind){
 const a=rad(lat),b=rad(lon)+state.angles[kind];
 const y=Math.sin(a),x=Math.cos(a)*Math.sin(b),z=Math.cos(a)*Math.cos(b);
 const pitch=state.pitches[kind],cp=Math.cos(pitch),sp=Math.sin(pitch);
 return {x,y:y*cp-z*sp,z:y*sp+z*cp};
}
function renderSphere(kind){
 const obj=globes[kind],canvas=obj.canvas,ctx=canvas.getContext("2d");
 const w=canvas.width,h=canvas.height,cx=w/2,cy=h/2,R=Math.min(w,h)*.365*state.zooms[kind];
 ctx.clearRect(0,0,w,h);obj.hits=[];
 const img=textures[obj.texture];
 ctx.save();ctx.beginPath();ctx.arc(cx,cy,R,0,TAU);ctx.clip();
 const base=kind==="earth"?"#244f8a":state.body==="mars"?"#a46142":"#aeb8c1";
 let grd=ctx.createRadialGradient(cx-R*.34,cy-R*.43,R*.04,cx+R*.3,cy+R*.22,R*1.55);
 grd.addColorStop(0,kind==="earth"?"#81b0dd":state.body==="mars"?"#e8ad7d":"#e4e7e9");
 grd.addColorStop(.7,base);grd.addColorStop(1,"#111923");
 ctx.fillStyle=grd;ctx.fillRect(cx-R,cy-R,2*R,2*R);
 if(img?.ready && img.naturalWidth){
  // Pixel-aligned projected map. Tile sampling avoids reading cross-origin image pixels.
  const step=8,cp=Math.cos(state.pitches[kind]),sp=Math.sin(state.pitches[kind]);
  for(let dy=-R;dy<R;dy+=step){
   for(let dx=-R;dx<R;dx+=step){
    const nx=(dx+step/2)/R,ny=-(dy+step/2)/R,dist=nx*nx+ny*ny;
    if(dist>1)continue;
    const nz=Math.sqrt(1-dist);
    const worldY=ny*cp+nz*sp;
    const worldZ=nz*cp-ny*sp;
    const latitude=Math.asin(Math.max(-1,Math.min(1,worldY)));
    const longitude=Math.atan2(nx,worldZ)-state.angles[kind];
    const sx=((longitude/TAU+.5)%1+1)%1*img.naturalWidth;
    const sy=(.5-latitude/Math.PI)*img.naturalHeight;
    try{ctx.drawImage(img,sx,sy,Math.min(7,img.naturalWidth-sx),7,cx+dx,cy+dy,step+1,step+1)}catch(e){}
   }
  }
 }
 // A restrained geographic grid assists orientation; it is not a data raster.
 ctx.strokeStyle="#d0e4f31a";ctx.lineWidth=.9;
 for(let lat=-60;lat<=60;lat+=30){
  ctx.beginPath();let started=false;
  for(let lon=-180;lon<=180;lon+=3){
   const p=globeProject(lat,lon,kind);if(p.z<0){started=false;continue}
   const x=cx+p.x*R,y=cy-p.y*R;
   if(!started){ctx.moveTo(x,y);started=true}else ctx.lineTo(x,y);
  }ctx.stroke();
 }
 for(let lon=-180;lon<180;lon+=30){
  ctx.beginPath();let started=false;
  for(let lat=-89;lat<=89;lat+=3){
   const p=globeProject(lat,lon,kind);if(p.z<0){started=false;continue}
   const x=cx+p.x*R,y=cy-p.y*R;
   if(!started){ctx.moveTo(x,y);started=true}else ctx.lineTo(x,y);
  }ctx.stroke();
 }
 const shadow=ctx.createRadialGradient(cx-R*.27,cy-R*.38,R*.07,cx+R*.22,cy+R*.15,R*1.32);
 shadow.addColorStop(0,"#0000");shadow.addColorStop(.62,"#0000000f");shadow.addColorStop(1,"#01060ec8");
 ctx.fillStyle=shadow;ctx.fillRect(cx-R,cy-R,R*2,R*2);
 ctx.restore();
 ctx.beginPath();ctx.arc(cx,cy,R,0,TAU);ctx.strokeStyle="#8db8d13e";ctx.lineWidth=1.4;ctx.stroke();
 const markers=kind==="target"?state.sites:state.candidates;
 const visible=[];
 for(const item of markers){
  if(!Number.isFinite(item.latitude)||!Number.isFinite(item.longitude))continue;
  const p=globeProject(item.latitude,item.longitude,kind);
  if(p.z<0.05)continue;
  const x=cx+p.x*R,y=cy-p.y*R;
  const selected=kind==="target"?state.site?.id===item.id:state.earth?.id===item.id;
  ctx.beginPath();ctx.arc(x,y,selected?7:4.5,0,TAU);
  ctx.fillStyle=selected?"#f9e1a8":kind==="earth"?"#8fdfbd":"#9ad4f6";ctx.fill();
  ctx.lineWidth=2;ctx.strokeStyle="#092234";ctx.stroke();
  visible.push({item,x,y,selected});
 }
 ctx.fillStyle="#e1f0f7";ctx.textBaseline="middle";ctx.font="11px system-ui";
 for(const p of visible.filter(x=>x.selected).concat(visible.filter(x=>!x.selected).slice(0,5))){
  const label=p.item.name.slice(0,28);
  const offset=p.x>cx+R*.35?-9-ctx.measureText(label).width:11;
  ctx.fillText(label,p.x+offset,p.y-12);
 }
 obj.hits=visible;
}
let lastRender=0;
function paintBoth(){renderSphere("target");renderSphere("earth")}
function centerGlobe(kind,item){
 if(!item)return;
 state.angles[kind]=-rad(item.longitude);
 state.pitches[kind]=Math.max(-1.25,Math.min(1.25,rad(item.latitude)));
 renderSphere(kind);
}
function resetGlobe(kind){
 state.zooms[kind]=1;
 if(kind==="target"&&state.site)centerGlobe(kind,state.site);
 else if(kind==="earth"&&state.earth)centerGlobe(kind,state.earth);
 else {state.angles[kind]=-.5;state.pitches[kind]=.15;renderSphere(kind)}
}
function setupPointer(kind){
 const obj=globes[kind],canvas=obj.canvas;
 canvas.addEventListener("pointerdown",e=>{obj.drag={x:e.clientX,y:e.clientY,moved:false};canvas.setPointerCapture(e.pointerId)});
 canvas.addEventListener("pointermove",e=>{
  if(!obj.drag)return;
  const dx=e.clientX-obj.drag.x,dy=e.clientY-obj.drag.y;
  if(Math.abs(dx)+Math.abs(dy)>2)obj.drag.moved=true;
  state.angles[kind]+=dx*.007;
  state.pitches[kind]=Math.max(-1.35,Math.min(1.35,state.pitches[kind]+dy*.007));
  obj.drag.x=e.clientX;obj.drag.y=e.clientY;renderSphere(kind);
 });
 canvas.addEventListener("pointerup",e=>{
  if(!obj.drag)return;
  const moved=obj.drag.moved;obj.drag=null;if(moved)return;
  const rect=canvas.getBoundingClientRect();
  const x=(e.clientX-rect.left)/rect.width*canvas.width,y=(e.clientY-rect.top)/rect.height*canvas.height;
  const hit=obj.hits.find(p=>Math.hypot(p.x-x,p.y-y)<17);
  if(hit){if(kind==="target")chooseSite(hit.item);else chooseEarth(hit.item)}
 });
 canvas.addEventListener("wheel",e=>{
  e.preventDefault();state.zooms[kind]=Math.min(1.22,Math.max(.64,state.zooms[kind]-e.deltaY*.0005));renderSphere(kind);
 },{passive:false});
}
function renderSites(){
 const box=$("target-sites");box.replaceChildren();
 state.sites.forEach(site=>{
  const button=document.createElement("button");button.type="button";button.textContent=site.name;
  button.classList.toggle("active",site.id===state.site?.id);
  button.onclick=()=>chooseSite(site);box.append(button);
 });
}
async function loadSites(body){
 const token=++state.requestToken;
 state.sites=[];state.candidates=[];state.site=null;state.earth=null;state.reference=null;state.evidence=null;
 $("target-sites").replaceChildren();
 setText("target-selection","Retrieving documented mission sites…");
 setText("earth-selection","Select a target site");
 setText("earth-coordinates","NASA/METI ASTER measured terrain");
 setText("target-source-status","SOURCE LOADING");setText("earth-source-status","AWAITING SITE");
 setText("telemetry-status","LOADING MISSION SITES");
 paintBoth();renderTelemetry();renderCandidates();
 try{
  const data=await json("/exploration/sites?body="+body);
  if(token!==state.requestToken)return;
  state.sites=data.sites||[];renderSites();paintBoth();
  const preferred=body==="moon"?"apollo-15":"perseverance";
  const site=state.sites.find(x=>x.id===preferred)||state.sites[0];
  if(site)chooseSite(site);
 }catch(error){
  if(token!==state.requestToken)return;
  setText("target-selection","Site service unavailable: "+error.message);
  setText("telemetry-status","SOURCE ERROR");
 }
}
async function chooseSite(site){
 state.site=site;state.earth=null;state.reference=null;state.candidates=[];state.evidence=null;
 const token=++state.requestToken;
 openData();
 setText("target-selection",site.name);
 setText("target-coordinates",coords(site)+(site.mission?" · "+site.mission:""));
 setText("earth-selection","Searching measured terrain…");
 setText("target-source-status","NASA REFERENCE");
 setText("earth-source-status","SEARCHING");
 setText("telemetry-status","MEASURING TERRAIN CANDIDATES");
 centerGlobe("target",site);renderSites();renderCandidates();renderTelemetry();
 try{
  const data=await json("/science/terrain-survey/candidates?body="+state.body+"&site_id="+encodeURIComponent(site.id)+"&limit=15");
  if(token!==state.requestToken)return;
  if(!data.ready||!data.results?.length){
   setText("earth-selection","No measured candidates for this site");
   setText("earth-source-status","NO MEASUREMENTS");setText("telemetry-status","DATA UNAVAILABLE");
   renderCandidates();renderTelemetry();return;
  }
  state.reference=data.reference;state.candidates=data.results;
  setText("target-source-status","NASA MEASURED DEM");
  setText("earth-source-status","ASTER SCREENING");
  setText("telemetry-status",data.count+" TERRAIN CANDIDATES");
  renderCandidates();chooseEarth(state.candidates[0]);
 }catch(error){
  if(token!==state.requestToken)return;
  setText("earth-selection","Scientific comparison unavailable: "+error.message);
  setText("telemetry-status","SOURCE ERROR");
 }
}
async function chooseEarth(earth){
 state.earth=earth;state.evidence=null;
 openData();
 setText("earth-selection",earth.name);
 setText("earth-coordinates",coords(earth)+" · "+(earth.search_stage==="coarse_to_fine_refinement"?"Refined Earth sample":"Global Earth sample"));
 centerGlobe("earth",earth);renderCandidates();renderTelemetry();
 loadEarthSnapshot(earth);
 const token=++state.evidenceToken;
 try{
  const data=await json("/science/analog-evidence?body="+state.body+
    "&site_id="+encodeURIComponent(state.site.id)+"&earth_id="+encodeURIComponent(earth.id));
  if(token!==state.evidenceToken||state.earth?.id!==earth.id)return;
  state.evidence=data;
  renderTelemetry();
 }catch(error){
  if(token!==state.evidenceToken)return;
  setText("evidence-warning","Evidence details unavailable: "+error.message+" · No suitability scores were inferred.");
 }
}
const domains=[
 {id:"habitat",title:"Habitat Construction & Sheltering",desc:"Topographic relief offers a preliminary site-access consideration. Bearing strength, radiation, atmosphere and construction resources are unmeasured."},
 {id:"rover",title:"Rover Mobility & Traction",desc:"Terrain variability can inform rover field-test design. Soil friction, surface rock sizes and actual traction are not measured."},
 {id:"isru",title:"In-Situ Resource Utilization (ISRU)",desc:"No verified resource grade, abundance, extractability or water-ice match. Terrain-only ranks cannot support ISRU readiness."},
 {id:"life",title:"Biosignature & Life Detection",desc:"No paired habitability or biology evidence; terrestrial life is not an indicator of life on the Moon or Mars."},
 {id:"drill",title:"Subsurface & Deep Drilling",desc:"Terrain context is available; subsurface stratigraphy, mechanical strength and drillability have not been measured."}
];
function renderMatrix(){
 const box=$("domain-matrix");box.replaceChildren();
 domains.forEach(domain=>{
  const item=document.createElement("div");item.className="domain-card";
  const head=document.createElement("div");head.className="domain-head";
  const title=document.createElement("strong");title.textContent=domain.title;
  const grade=document.createElement("em");grade.textContent=domain.id==="rover"||domain.id==="habitat"||domain.id==="drill"?"TERRAIN CONTEXT ONLY":"NO COMPARABLE DATA";
  head.append(title,grade);
  const note=document.createElement("p");note.textContent=domain.desc;
  item.append(head,note);box.append(item);
 });
}
function renderTelemetry(){
 const a=state.reference?.stats,b=state.earth?.stats;
 setText("popup-target",state.site?.name||"PLANETARY SITE");
 setText("popup-earth",state.earth?.name||"EARTH CANDIDATE");
 setText("distance-score",state.earth?Number(state.earth.terrain_distance).toFixed(3):"—");
 setText("target-relief",a?Number(a.relief_m).toLocaleString():"—");
 setText("earth-relief",b?Number(b.relief_m).toLocaleString():"—");
 setText("target-roughness",a?Number(a.height_std_m).toLocaleString():"—");
 setText("earth-roughness",b?Number(b.height_std_m).toLocaleString():"—");
 setText("distance-status",state.earth&&state.reference?
  "Terrain only · 2 measured features. Lower distance means closer terrain variation, NOT a similarity %.":
  "Select a site to compare measured terrain.");
 $("query-elevation").disabled=!state.earth;
 $("planet-data-link").href=state.reference?.source_url||"https://pds.nasa.gov/";
 $("earth-data-link").href=state.earth?.source_url||"https://www.opentopodata.org/datasets/aster/";
 setText("evidence-warning",state.evidence?.ready?
  "Key limitations: "+Object.values(state.evidence.where_analogy_breaks_down.physical_environment_mismatches).join(" "):
  "Earth cannot reproduce reduced lunar/Martian gravity, lunar vacuum, thin Martian atmosphere, or space radiation.");
 renderMatrix();
}
function renderCandidates(){
 const list=$("candidate-list"),query=$("candidate-search").value.trim().toLowerCase();
 list.replaceChildren();
 const domain=state.filter;
 const supported=domain==="all"||domain==="rover"||domain==="habitat"||domain==="drill";
 if(!supported){
  const p=document.createElement("p");p.className="muted";
  p.textContent="No verified "+(domain==="life"?"biosignature":"ISRU")+" dataset is used to rank these locations. Select ALL for terrain-based candidates.";
  list.append(p);setText("candidate-count","0 EVIDENCE-SUPPORTED RESULTS");return;
 }
 const rows=state.candidates.filter(c=>c.name.toLowerCase().includes(query)||coords(c).toLowerCase().includes(query));
 setText("candidate-count",rows.length+" TERRAIN CANDIDATES");
 if(!rows.length){const p=document.createElement("p");p.className="muted";p.textContent="No measured candidates match this search.";list.append(p);return}
 rows.forEach((item,i)=>{
  const button=document.createElement("button");button.type="button";button.className="candidate";
  button.classList.toggle("active",state.earth?.id===item.id);
  const rank=document.createElement("span");rank.className="rank";rank.textContent=String(state.candidates.indexOf(item)+1).padStart(2,"0");
  const inf=document.createElement("span");inf.className="candidate-info";
  const title=document.createElement("strong");title.textContent=item.name;
  const sub=document.createElement("small");sub.textContent=coords(item)+" · "+(item.search_stage?"Refined":"Global")+" terrain";
  inf.append(title,sub);
  const score=document.createElement("span");score.className="score";score.textContent=Number(item.terrain_distance).toFixed(3);
  const small=document.createElement("small");small.textContent="DISTANCE ↓";score.append(small);
  button.append(rank,inf,score);button.onclick=()=>chooseEarth(item);list.append(button);
 });
}
async function loadEarthSnapshot(earth){
 const token=++state.snapshotToken;
 const button=$("query-elevation");
 button.disabled=true;
 setText("earth-temp","…");
 setText("earth-point-elevation","…");
 setText("elevation-result","Loading NASA POWER air temperature and Earth DEM point elevation…");
 try{
  const data=await json("/science/earth-environment?latitude="+earth.latitude+
    "&longitude="+earth.longitude);
  if(token!==state.snapshotToken||state.earth!==earth)return;
  const temp=data.measurements?.T2M?.value, elevation=data.measurements?.DEM_ELEVATION;
  setText("earth-temp",Number.isFinite(temp)?Number(temp).toFixed(1)+" °C":"N/A");
  setText("earth-point-elevation",Number.isFinite(elevation?.value)?
    Math.round(elevation.value).toLocaleString()+" m":"N/A");
  setText("elevation-result","Earth temperature: NASA POWER, January 2025 (2m air). Elevation: "+
   (elevation?.source||"unavailable")+". Neither is a measured Moon/Mars temperature match.");
 }catch(error){
  if(token!==state.snapshotToken||state.earth!==earth)return;
  setText("earth-temp","N/A");
  setText("earth-point-elevation","N/A");
  setText("elevation-result","Earth data unavailable ("+error.message+"). No estimated values shown.");
 }finally{
  if(token===state.snapshotToken)button.disabled=!state.earth;
 }
}
async function queryElevation(){
 if(state.earth)await loadEarthSnapshot(state.earth);
}
async function checkConnection(){
 try{
  const [health,survey]=await Promise.all([json("/health"),json("/science/terrain-survey/status")]);
  const okay=survey.ready===true;const dot=document.querySelector(".connection-dot");dot.classList.toggle("active",okay);
  setText("connection-status",okay?"● NASA LOLA / MOLA + ASTER BATCH READY":"● DATA SERVICE PARTIAL");
  setText("coverage-count",okay?"1 / 8 DOMAINS":"NO MEASURED BATCH");
 }catch(e){setText("connection-status","● OFFLINE / SERVICE UNAVAILABLE");}
}
for(const kind of ["target","earth"]){setupPointer(kind);$("reset-"+kind).addEventListener("click",()=>resetGlobe(kind))}
$("target-moon").addEventListener("click",()=>setBody("moon"));
$("target-mars").addEventListener("click",()=>setBody("mars"));
for(const mode of ["dual","target","earth"])$("mode-"+mode).addEventListener("click",()=>setMode(mode));
$("orbit-switch").addEventListener("click",()=>{
 state.orbit=!state.orbit;
 const b=$("orbit-switch");b.setAttribute("aria-pressed",String(state.orbit));b.textContent="● ORBIT: "+(state.orbit?"ON":"OFF");
});
$("drawer-toggle").addEventListener("click",closeData);
$("show-data").addEventListener("click",openData);
document.addEventListener("keydown",event=>{
 if(event.key==="Escape"&&!$("telemetry").hidden)closeData();
});
$("query-elevation").addEventListener("click",queryElevation);
$("candidate-search").addEventListener("input",renderCandidates);
for(const b of document.querySelectorAll("#domain-filters .filter"))b.addEventListener("click",()=>{
 state.filter=b.dataset.domain;document.querySelectorAll("#domain-filters .filter").forEach(x=>x.classList.toggle("active",x===b));renderCandidates();
});
if(!window.matchMedia("(prefers-reduced-motion: reduce)").matches){
 setInterval(()=>{if(!state.orbit||globes.target.drag||globes.earth.drag)return;
  state.angles.target+=.018;state.angles.earth+=.012;paintBoth();
 },95);
}
renderMatrix();paintBoth();checkConnection();setBody("moon");