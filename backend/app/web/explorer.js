"use strict";
// Moon-first interactive research viewer. Navigation sites are not similarity claims.
const $=id=>document.getElementById(id);
const state={target:"moon",view:"planet",sites:[],earth:[],reference:null,selected:null,angle:-.5,pitch:.18,zoom:1,drag:null,busy:false,token:0,screening:null,selectedSite:null,measurements:null,measureLoading:false,measureSeq:0,surveyMode:"qualitative",mro:null,mroLoading:false,mroSeq:0};
const canvas=$("globe"),ctx=canvas.getContext("2d");
const TAU=Math.PI*2;
const rad=v=>v*Math.PI/180;
const fmt=p=>p.latitude.toFixed(3)+"°, "+p.longitude.toFixed(3)+"°";
const escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function request(path){const res=await fetch(path);if(!res.ok)throw Error("HTTP "+res.status);return res.json();}
function project(p){
 const lat=rad(p.latitude),lon=rad(p.longitude)+state.angle,cp=Math.cos(state.pitch),sp=Math.sin(state.pitch);
 const x=Math.cos(lat)*Math.sin(lon),y=Math.sin(lat),z=Math.cos(lat)*Math.cos(lon);
 const yr=y*cp-z*sp, zr=y*sp+z*cp;
 return {x:x,y:yr,z:zr};
}
function points(){return state.view==="planet"?state.sites:state.earth;}
// NASA-derived visual maps, distributed by Solar System Scope under CC BY 4.0.
// Geographic features are visual references, not scientific analysis rasters.
const textureURLs={
 moon:"https://www.solarsystemscope.com/textures/download/2k_moon.jpg",
 mars:"https://www.solarsystemscope.com/textures/download/2k_mars.jpg",
 earth:"https://www.solarsystemscope.com/textures/download/2k_earth_daymap.jpg"
};
const textureImages={};
for(const [key,url] of Object.entries(textureURLs)){
 const img=new Image();
 img.onload=()=>{textureImages[key]=img;render();};
 img.onerror=()=>{console.warn("PLANETREX surface image unavailable:",key);};
 img.src=url;
}
// Perspective-correct sphere mapping. Each visible pixel tile is sampled from
// the corresponding equirectangular longitude/latitude position. No fictional
// surface details are drawn when the real map hasn't loaded.
function paintSphereMap(key,cx,cy,radius){
 const image=textureImages[key];if(!image?.naturalWidth)return false;
 const step=5,cp=Math.cos(state.pitch),sp=Math.sin(state.pitch);
 ctx.save();ctx.beginPath();ctx.arc(cx,cy,radius,0,TAU);ctx.clip();
 for(let y=Math.floor(cy-radius);y<cy+radius;y+=step){
  const py=y+step*.5;
  const ny=(cy-py)/radius,ny2=ny*ny;
  if(ny2>=1)continue;
  const maxX=radius*Math.sqrt(1-ny2);
  for(let x=Math.floor(cx-maxX);x<cx+maxX;x+=step){
   const px=x+step*.5;
   const nx=(px-cx)/radius,z2=1-nx*nx-ny2;
   if(z2<=0)continue;
   const z=Math.sqrt(z2);
   const unpitchedY=Math.max(-1,Math.min(1,ny*cp+z*sp));
   const unpitchedZ=-ny*sp+z*cp;
   const longitude=Math.atan2(nx,unpitchedZ)-state.angle;
   const u=((longitude/TAU+0.5)%1+1)%1;
   const v=0.5-Math.asin(unpitchedY)/Math.PI;
   const sx=Math.min(image.naturalWidth-2,Math.max(0,Math.floor(u*image.naturalWidth)));
   const sy=Math.min(image.naturalHeight-2,Math.max(0,Math.floor(v*image.naturalHeight)));
   ctx.drawImage(image,sx,sy,Math.min(5,image.naturalWidth-sx),Math.min(5,image.naturalHeight-sy),x,y,step+1,step+1);
  }
 }
 const shadow=ctx.createRadialGradient(cx-radius*.26,cy-radius*.34,radius*.13,cx+radius*.2,cy+radius*.1,radius*1.25);
 shadow.addColorStop(0,"rgba(0,0,0,0)");shadow.addColorStop(.62,"rgba(0,0,0,.12)");shadow.addColorStop(1,"rgba(2,7,16,.64)");
 ctx.fillStyle=shadow;ctx.fillRect(cx-radius,cy-radius,radius*2,radius*2);
 ctx.restore();return true;
}

function render(){
 const w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);
 const R=Math.min(w,h)*.37*state.zoom,cx=w/2,cy=h/2;
 const earth=state.view==="earth",mars=state.view==="planet"&&state.target==="mars";
 const base=earth?"#265f91":mars?"#ad593d":"#9da6b0";
 const shade=ctx.createRadialGradient(cx-R*.38,cy-R*.45,R*.1,cx,cy,R*1.4);
 shade.addColorStop(0,earth?"#6db6d8":mars?"#d18b68":"#d4d7da");
 shade.addColorStop(.62,base);shade.addColorStop(1,"#111722");
 ctx.beginPath();ctx.arc(cx,cy,R,0,TAU);ctx.fillStyle=shade;ctx.fill();
 const hasTexture=paintSphereMap(earth?"earth":mars?"mars":"moon",cx,cy,R);
 ctx.save();ctx.beginPath();ctx.arc(cx,cy,R,0,TAU);ctx.clip();
 // Rotation-responsive graticule and terrain shading; illustrative texture only.
 ctx.strokeStyle=hasTexture?"#a5d6f310":earth?"#79b6d733":"#111a2530";ctx.lineWidth=1;
 for(let lat=-75;lat<=75;lat+=15){ctx.beginPath();let started=false;
  for(let lon=-180;lon<=180;lon+=3){const p=project({latitude:lat,longitude:lon});if(p.z<=0){started=false;continue}
   const x=cx+p.x*R,y=cy-p.y*R;if(!started){ctx.moveTo(x,y);started=true}else ctx.lineTo(x,y)}
  ctx.stroke();}
 for(let lon=-180;lon<180;lon+=15){ctx.beginPath();let started=false;
  for(let lat=-90;lat<=90;lat+=3){const p=project({latitude:lat,longitude:lon});if(p.z<=0){started=false;continue}
   const x=cx+p.x*R,y=cy-p.y*R;if(!started){ctx.moveTo(x,y);started=true}else ctx.lineTo(x,y)}
  ctx.stroke();}
 ctx.restore();
 let visible=[];
 for(const loc of points()){const p=project(loc);if(p.z<0.04)continue;const x=cx+p.x*R,y=cy-p.y*R;
  ctx.beginPath();ctx.arc(x,y,state.selected?.id===loc.id?8:5,0,TAU);ctx.fillStyle=earth?"#75d5be":mars?"#ffbd7a":"#9bd5ff";ctx.fill();ctx.strokeStyle="#092033";ctx.lineWidth=2;ctx.stroke();
  visible.push({loc,x,y});}
 ctx.font="12px system-ui";ctx.textBaseline="middle";
 for(const item of visible.slice(0,10)){let x=item.x+10,y=item.y;if(x+130>w)x=item.x-128;
  ctx.fillStyle="#e7f3ff";ctx.fillText((item.loc.name+(typeof item.loc.tag_overlap_percent==="number"?" · "+item.loc.tag_overlap_percent+"%":"")).slice(0,34),x,y,152);}
 state.hits=visible;
}
function updateHeader(){
 const planet=state.view==="planet",name=state.target==="moon"?"Moon":"Mars";
 $("moon-tab").classList.toggle("active",state.target==="moon");
 $("mars-tab").classList.toggle("active",state.target==="mars");
 $("globe-name").textContent=planet?name.toUpperCase():"EARTH";
 $("mode-label").textContent=planet?"SELECT A "+(state.target==="moon"?"LUNAR":"MARTIAN")+" REGION":name.toUpperCase()+" → EARTH";
 $("page-heading").textContent=planet?"Explore "+(state.target==="moon"?"the Moon":"Mars"):"Earth counterparts";
 $("page-subtitle").textContent=planet?"Select one of the documented locations or rotate the globe.":"Earth candidates ranked by NASA terrain measurement distance where available; otherwise preliminary descriptor overlap.";
 $("side-title").textContent=planet?name+" mission sites":"Earth analog candidates";
 $("side-type").textContent=planet?"DOCUMENTED NAVIGATION SITES":"PRELIMINARY FEATURE MATCHES";
 $("side-description").textContent=planet?"Select a named landing site, or click a region on the globe.":"Automatic global topography screening where measured data exists; otherwise descriptive feature-tag overlap.";
 $("back-button").classList.toggle("hidden",planet);
}
function renderList(){
 const list=$("locations");list.replaceChildren();
 const q=$("location-search").value.toLowerCase();
 const matches=points().filter(x=>x.name.toLowerCase().includes(q));
 $("list-label").textContent=matches.length+" "+(state.view==="planet"?"NAVIGATION SITES":"EVIDENCE-SCREENED CANDIDATES");
 if(!matches.length){const p=document.createElement("p");p.className="empty";p.textContent=state.view==="earth"?(state.screening?.message||"No evidenced matches for this location."):"No matching sites.";list.append(p);}
 matches.forEach((item,i)=>{const b=document.createElement("button");b.type="button";b.className="location";if(state.selected?.id===item.id)b.classList.add("selected");
 const info=document.createElement("span"),title=document.createElement("b"),sub=document.createElement("small");
 title.textContent=item.name;sub.textContent=(item.mission?item.mission+" · ":"")+fmt(item)+(typeof item.terrain_distance==="number"?" · distance "+item.terrain_distance.toFixed(2):typeof item.tag_overlap_percent==="number"?" · "+item.tag_overlap_percent+"% tag overlap":"");info.append(title,sub);b.append(info);const num=document.createElement("small");num.textContent=typeof item.terrain_distance==="number"?item.terrain_distance.toFixed(2):typeof item.tag_overlap_percent==="number"?item.tag_overlap_percent+"%":String(i+1).padStart(2,"0");b.append(num);
 b.addEventListener("click",()=>choose(item));list.append(b);});
}
function details(){
 const d=$("details");d.replaceChildren();const title=document.createElement("b");title.textContent=state.view==="planet"?"Select a region":"Selected planetary reference";d.append(title);
 const p=document.createElement("p");
 p.textContent=state.view==="planet"?"Navigation markers show documented site locations, not scientific matches.":state.reference?"Measured reference: "+state.reference.name:"Descriptive geological feature screening only; quantitative planetary reference measurements are not yet integrated.";
 d.append(p);
 if(state.view==="earth" && state.screening){
  const summary=document.createElement("p");summary.textContent=state.screening.percent_meaning||"";d.append(summary);
  if(state.selectedSite){
   const location=document.createElement("p");location.textContent="Planetary location: "+state.selectedSite.name;d.append(location);
  }
 }
 if(state.view==="earth" && state.target==="mars"){
  const h=document.createElement("b");h.textContent="NASA MRO CTX · High-resolution Mars terrain";d.append(h);
  if(state.mroLoading){
   const p=document.createElement("p");p.textContent="Checking MRO CTX stereo coverage…";d.append(p);
  }else if(state.mro){
   const p=document.createElement("p");p.textContent=state.mro.count+" published stereo DTM footprint(s) found near "+state.mro.site_name+
     ". Catalogue only — not used in the score.";d.append(p);
   for(const item of (state.mro.products||[]).slice(0,3)){
    const a=document.createElement("a");a.href=item.source_url;a.target="_blank";a.rel="noopener noreferrer";
    a.textContent=(item.title||item.id).slice(0,65);d.append(a,document.createElement("div"));
   }
   const x=document.createElement("p");x.textContent="20m-post CTX stereo models exist in this archive, but individual elevations and quality masks are not yet harmonized into our ranking.";d.append(x);
  }
 }
  if(state.view==="earth"){
  const heading=document.createElement("b");heading.textContent="Measured Earth observations";d.append(heading);
  if(!state.selected){const help=document.createElement("p");help.textContent="Select an Earth candidate to load NASA POWER and Copernicus DEM observations.";d.append(help);}
  else if(state.measureLoading){const help=document.createElement("p");help.textContent="Retrieving independently sourced Earth measurements…";d.append(help);}
  else if(state.measurements){
   const info=state.measurements;
   const heading2=document.createElement("p");heading2.textContent="Measurement status: "+info.status+" · "+info.source_count+"/2 sources responding";d.append(heading2);
   for(const [code,measurement] of Object.entries(info.measurements||{})){
    const line=document.createElement("p");
    line.textContent=measurement.label+": "+(measurement.value==null?"Unavailable":measurement.value+" "+measurement.unit);
    d.append(line);
    const note=document.createElement("small");note.textContent=measurement.source+" · "+(measurement.period||measurement.source_data||"point sample");d.append(note);
    const link=document.createElement("a");link.href=measurement.source_url;link.rel="noopener noreferrer";link.target="_blank";link.textContent=" Dataset source";d.append(document.createTextNode(" "),link);
   }
   for(const err of info.source_errors||[]){const message=document.createElement("p");message.textContent="Source unavailable: "+err.source+" ("+err.reason+")";d.append(message);}
   const warning=document.createElement("p");warning.textContent="These are real Earth measurements. A physically measured Moon/Mars comparison is not yet available.";d.append(warning);
  }
 }
 if(state.selected && typeof state.selected.terrain_distance==="number"){
  const ref=state.reference;
  const label=document.createElement("p");label.textContent="Measured NASA–ASTER terrain screening · lower distance = closer topographic variation. Not a physical similarity %.";d.append(label);
  const value=document.createElement("p");value.textContent="Terrain distance: "+state.selected.terrain_distance.toFixed(4)+" (uncalibrated, dimensionless). Coverage: 2 of 8 planned feature dimensions.";d.append(value);
  const row=document.createElement("p");row.textContent="Earth 24km window: relief "+state.selected.stats.relief_m+"m, vertical SD "+state.selected.stats.height_std_m+"m.";d.append(row);
  if(ref?.stats){const r=document.createElement("p");r.textContent=ref.name+" NASA "+ref.dataset+": relief "+ref.stats.relief_m+"m; vertical SD "+ref.stats.height_std_m+"m.";d.append(r);}
  for(const source of [ref?.source_url,state.selected.source_url]){
   if(source?.startsWith("https://")){const a=document.createElement("a");a.href=source;a.target="_blank";a.rel="noopener noreferrer";a.textContent="DEM source";d.append(a,document.createTextNode("  "));}
  }
  const note=document.createElement("p");note.textContent="Screened automatically across coarse global Earth cells; terrain-only lead, not a verified analog, mineralogy match, landing recommendation or habitable base.";d.append(note);
 }
 if(state.selected && typeof state.selected.tag_overlap_percent==="number"){
  const score=document.createElement("p");score.textContent=state.selected.tag_overlap_percent+"% documented feature-tag overlap · "+state.selected.overlap_fraction+" shared/total features";d.append(score);
  const matched=document.createElement("p");matched.textContent="Shared features: "+state.selected.matching_features.join(", ");d.append(matched);
  const caveat=document.createElement("p");caveat.textContent="NOT a measured scientific similarity percentage.";d.append(caveat);
  for(const url of [state.selected.reference_source_url,state.selected.earth_source_url]){
   if(url?.startsWith("https://")){const a=document.createElement("a");a.href=url;a.target="_blank";a.rel="noopener noreferrer";a.textContent="View evidence source";d.append(a,document.createTextNode("  "));}
  }
 }
 if(state.selected){const v=document.createElement("p");v.textContent="Earth location: "+state.selected.name+" ("+fmt(state.selected)+")";d.append(v);
  if(state.selected.features){for(const [key,value] of Object.entries(state.selected.features)){const r=document.createElement("p");r.textContent=key+": "+value.value+" "+value.unit;d.append(r);}}}
}
function paint(){updateHeader();renderList();details();render();}
async function loadPlanet(target){
 const token=++state.token;Object.assign(state,{target,view:"planet",sites:[],earth:[],reference:null,selected:null,selectedSite:null,screening:null,measurements:null,measureLoading:false,surveyMode:"qualitative",mro:null,mroLoading:false,angle:-.5,pitch:.18,zoom:1});
 $("location-search").value="";paint();
 try{const data=await request("/exploration/sites?body="+target);if(token!==state.token)return;state.sites=data.sites;paint();refreshLive();}
 catch(e){$("list-label").textContent="Unable to load sites: "+e.message;}
}
async function choose(item){
 if(state.view==="earth"){
  state.selected=item;state.measurements=null;state.angle=-rad(item.longitude);state.pitch=rad(item.latitude);paint();loadEarthMeasurements(item);return;
 }
 const token=++state.token;
 state.view="earth";state.reference=null;state.selected=null;state.selectedSite=item;
 state.screening=null;state.earth=[];state.mro=null;state.mroLoading=state.target==="mars";
 $("location-search").value="";paint();
 if(state.target==="mars")loadMROContext(item);
 try{
  const measured=await request("/science/terrain-survey/candidates?body="+state.target+"&site_id="+encodeURIComponent(item.id));
  if(token!==state.token)return;
  if(measured.ready && measured.results?.length){
   state.surveyMode="measured";state.screening=measured;state.reference=measured.reference;
   state.earth=measured.results;
  }else{
   const data=await request("/science/analog-screening?body="+state.target+"&site_id="+encodeURIComponent(item.id));
   if(token!==state.token)return;
   state.surveyMode="qualitative";state.screening=data;state.reference=null;state.earth=data.results||[];
  }
  if(state.earth.length){state.selected=state.earth[0];loadEarthMeasurements(state.earth[0]);}
  if(state.earth.length){state.angle=-rad(state.earth[0].longitude);state.pitch=rad(state.earth[0].latitude);}
  paint();
 }catch(e){$("list-label").textContent="Unable to load evidence screening: "+e.message;}
}

async function loadMROContext(site){
 const seq=++state.mroSeq;
 state.mro=null;state.mroLoading=true;details();
 try{
  const data=await request("/science/mro-ctx?site_id="+encodeURIComponent(site.id)+"&limit=5");
  if(seq!==state.mroSeq || state.selectedSite?.id!==site.id)return;
  state.mro=data;
 }catch(e){
  if(seq!==state.mroSeq)return;
  state.mro={count:0,products:[],site_name:site.name,error:e.message};
 }
 if(seq!==state.mroSeq)return;
 state.mroLoading=false;details();
}

async function loadEarthMeasurements(item){
 const seq=++state.measureSeq;
 state.measureLoading=true;state.measurements=null;details();
 try{
  const data=await request("/science/earth-environment?latitude="+item.latitude+"&longitude="+item.longitude);
  if(seq!==state.measureSeq||state.selected?.id!==item.id)return;
  state.measurements=data;
 }catch(error){
  if(seq!==state.measureSeq)return;
  state.measurements={status:"unavailable",source_count:0,measurements:{},
    source_errors:[{source:"Earth measurement services",reason:error.message}]};
 }
 if(seq!==state.measureSeq)return;
 state.measureLoading=false;details();
}

$("moon-tab").addEventListener("click",()=>loadPlanet("moon"));$("mars-tab").addEventListener("click",()=>loadPlanet("mars"));
$("back-button").addEventListener("click",()=>loadPlanet(state.target));$("reset-button").addEventListener("click",()=>{state.angle=-.5;state.pitch=.18;state.zoom=1;render()});
$("location-search").addEventListener("input",renderList);
canvas.addEventListener("pointerdown",e=>{state.drag={x:e.clientX,y:e.clientY,moved:false};canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener("pointermove",e=>{if(!state.drag)return;let dx=e.clientX-state.drag.x,dy=e.clientY-state.drag.y;if(Math.abs(dx)+Math.abs(dy)>3)state.drag.moved=true;state.angle+=dx*.007;state.pitch=Math.max(-1.3,Math.min(1.3,state.pitch+dy*.007));state.drag.x=e.clientX;state.drag.y=e.clientY;render();});
canvas.addEventListener("pointerup",e=>{if(!state.drag)return;const moved=state.drag.moved;state.drag=null;if(moved)return;const rect=canvas.getBoundingClientRect();const x=(e.clientX-rect.left)/rect.width*canvas.width,y=(e.clientY-rect.top)/rect.height*canvas.height;const hit=(state.hits||[]).find(p=>Math.hypot(p.x-x,p.y-y)<15);if(hit)choose(hit.loc)});
canvas.addEventListener("wheel",e=>{e.preventDefault();state.zoom=Math.max(.65,Math.min(1.2,state.zoom-e.deltaY*.0004));render()},{passive:false});
loadPlanet("moon");

const liveData={earth:[],pds:[]};
let liveRequestCounter=0;
function putText(id,value,isError=false){
 const node=$(id);if(!node)return;node.textContent=value;node.classList.toggle("error",isError);
}
function addResult(container,title,meta,linkText,href){
 const item=document.createElement("div");item.className="live-result";
 const b=document.createElement("b");b.textContent=title;item.append(b);
 const sm=document.createElement("small");sm.textContent=meta;item.append(sm);
 if(typeof href==="string"&&href.startsWith("https://")){
  const a=document.createElement("a");a.href=href;a.textContent=linkText||"Source";a.target="_blank";a.rel="noopener noreferrer";item.append(a);
 }
 container.append(item);
}
async function refreshLive(){
 const seq=++liveRequestCounter,button=$("refresh-live");button.disabled=true;
 putText("live-state","Contacting NASA...");
 putText("earth-source-status","Requesting current NASA EONET events...");
 putText("pds-source-status","Requesting "+state.target.toUpperCase()+" NASA imagery archive...");
 putText("cmr-source-status","Searching NASA Earthdata terrain collections...");
 $("pds-title").textContent=(state.target==="moon"?"Moon":"Mars")+" · NASA Image Library";
 $("earth-events").replaceChildren();$("pds-products").replaceChildren();$("cmr-products").replaceChildren();
 const outcomes=await Promise.allSettled([
  request("/scientific/earth-events?limit=30"),
  request("/scientific/nasa-imagery?target="+state.target+"&limit=12"),
  request("/science/earthdata-catalog?keyword=elevation&limit=6")
 ]);
 if(seq!==liveRequestCounter)return;
 const [earth,pds,cmr]=outcomes;
 let successes=0;
 if(earth.status==="fulfilled"){
  successes++;
  const payload=earth.value;liveData.earth=payload.events||[];
  putText("earth-source-status",liveData.earth.length+" mapped event(s) · retrieved "+new Date(payload.retrieved_at).toLocaleString());
  const node=$("earth-events");if(!liveData.earth.length)addResult(node,"No current point events","API responded, but no point geometry was returned.");
  for(const event of liveData.earth.slice(0,30)){
   const category=(event.categories||[]).join(", ")||"Natural event";
   const coords=Number(event.latitude).toFixed(2)+"°, "+Number(event.longitude).toFixed(2)+"°";
   addResult(node,event.title,category+" · "+coords+" · "+(event.date||"Date unavailable"),"View source",event.source_url);
  }
 }else{
  putText("earth-source-status","NASA EONET unavailable: "+earth.reason.message,true);
  addResult($("earth-events"),"Source temporarily unavailable","No placeholder events shown. Click Refresh to retry.");
 }
 if(pds.status==="fulfilled"){
  successes++;
  const payload=pds.value;liveData.pds=payload.products||[];
  putText("pds-source-status",liveData.pds.length+" archive record(s) · retrieved "+new Date(payload.retrieved_at).toLocaleString());
  const node=$("pds-products");if(!liveData.pds.length)addResult(node,"No indexed products returned","NASA PDS responded with no products for this request.");
  for(const p of liveData.pds.slice(0,12))addResult(node,p.title,p.id+" · "+(p.date_created||"Date unknown"),"View NASA source",p.source_url);
 }else{
  putText("pds-source-status","NASA imagery unavailable: "+pds.reason.message,true);
  addResult($("pds-products"),"NASA imagery request failed","No fabricated planetary measurements; source remains available via the link below.");
 }
 if(cmr.status==="fulfilled"){
  successes++;
  const payload=cmr.value,records=payload.collections||[];
  putText("cmr-source-status",records.length+" catalog records · retrieved "+new Date(payload.retrieved_at).toLocaleString());
  if(!records.length)addResult($("cmr-products"),"No catalog results","NASA Earthdata returned an empty search.");
  for(const entry of records)addResult($("cmr-products"),entry.title||entry.id,
     (entry.short_name||"")+(entry.version?" · v"+entry.version:""),
     "NASA Earthdata catalog",entry.catalog_url);
 }else{
  putText("cmr-source-status","NASA Earthdata unavailable: "+cmr.reason.message,true);
  addResult($("cmr-products"),"Catalog request failed","No replacement observations were fabricated.");
 }
 putText("live-state",successes+"/3 NASA data services responding");
 button.disabled=false;
}
$("refresh-live").addEventListener("click",refreshLive);
refreshLive();


async function checkGlobalTerrainSurvey(){
 const el=$("survey-data-status");if(!el)return;
 try{
  const survey=await request("/science/terrain-survey/status");
  if(survey.ready){
   const c=survey.global_scan, refinement=survey.refinement;
   el.classList.remove("error");
   el.textContent="Measured DEM survey ready · "+c.cells_with_terrain_coverage+" Earth candidate cells with terrain measurements / "+c.grid_cells_attempted+" systematically screened worldwide · "+survey.planetary_reference_count+" measured Moon/Mars reference footprints"+(refinement?" · "+refinement.usable_cells+" refined Earth candidate cells":"")+" · built "+new Date(survey.built_at).toLocaleString()+".";
  }else{
   el.classList.add("error");
   el.textContent="The measurement batch has not been published yet. Descriptive geological screening remains available; no invented terrain results are shown.";
  }
 }catch(e){el.classList.add("error");el.textContent="Terrain survey status unavailable: "+e.message;}
}
checkGlobalTerrainSurvey();
