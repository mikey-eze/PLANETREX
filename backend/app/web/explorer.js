"use strict";
// Moon-first interactive research viewer. Navigation sites are not similarity claims.
const $=id=>document.getElementById(id);
const state={target:"moon",view:"planet",sites:[],earth:[],reference:null,selected:null,angle:-.5,pitch:.18,zoom:1,drag:null,busy:false,token:0};
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
function render(){
 const w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);
 const R=Math.min(w,h)*.37*state.zoom,cx=w/2,cy=h/2;
 const earth=state.view==="earth",mars=state.view==="planet"&&state.target==="mars";
 const base=earth?"#265f91":mars?"#ad593d":"#9da6b0";
 const shade=ctx.createRadialGradient(cx-R*.38,cy-R*.45,R*.1,cx,cy,R*1.4);
 shade.addColorStop(0,earth?"#6db6d8":mars?"#d18b68":"#d4d7da");
 shade.addColorStop(.62,base);shade.addColorStop(1,"#111722");
 ctx.beginPath();ctx.arc(cx,cy,R,0,TAU);ctx.fillStyle=shade;ctx.fill();
 ctx.save();ctx.beginPath();ctx.arc(cx,cy,R,0,TAU);ctx.clip();
 // Rotation-responsive graticule and terrain shading; illustrative texture only.
 ctx.strokeStyle=earth?"#79b6d733":"#111a2530";ctx.lineWidth=1;
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
  ctx.fillStyle="#e7f3ff";ctx.fillText(item.loc.name.slice(0,23),x,y,130);}
 state.hits=visible;
}
function updateHeader(){
 const planet=state.view==="planet",name=state.target==="moon"?"Moon":"Mars";
 $("moon-tab").classList.toggle("active",state.target==="moon");
 $("mars-tab").classList.toggle("active",state.target==="mars");
 $("globe-name").textContent=planet?name.toUpperCase():"EARTH";
 $("mode-label").textContent=planet?"SELECT A "+(state.target==="moon"?"LUNAR":"MARTIAN")+" REGION":name.toUpperCase()+" → EARTH";
 $("page-heading").textContent=planet?"Explore "+(state.target==="moon"?"the Moon":"Mars"):"Earth counterparts";
 $("page-subtitle").textContent=planet?"Choose a named mission location or click the globe.":"Only stored, measured Earth profiles appear below. Unassessed grid cells are not analog matches.";
 $("side-title").textContent=planet?name+" mission sites":"Stored Earth locations";
 $("side-type").textContent=planet?"DOCUMENTED NAVIGATION SITES":"MEASURED EARTH PROFILES";
 $("side-description").textContent=planet?"Select a named landing site, or click a region on the globe.":"Scientific rankings require a measured planetary reference.";
 $("back-button").classList.toggle("hidden",planet);
}
function renderList(){
 const list=$("locations");list.replaceChildren();
 const q=$("location-search").value.toLowerCase();
 const matches=points().filter(x=>x.name.toLowerCase().includes(q));
 $("list-label").textContent=matches.length+" "+(state.view==="planet"?"NAVIGATION SITES":"EARTH PROFILES");
 if(!matches.length){const p=document.createElement("p");p.className="empty";p.textContent=state.view==="earth"?"No processed Earth profiles yet. The discovery pipeline must run first.":"No matching sites.";list.append(p);}
 matches.forEach((item,i)=>{const b=document.createElement("button");b.type="button";b.className="location";if(state.selected?.id===item.id)b.classList.add("selected");
 const info=document.createElement("span"),title=document.createElement("b"),sub=document.createElement("small");
 title.textContent=item.name;sub.textContent=(item.mission?item.mission+" · ":"")+fmt(item);info.append(title,sub);b.append(info);const num=document.createElement("small");num.textContent=String(i+1).padStart(2,"0");b.append(num);
 b.addEventListener("click",()=>choose(item));list.append(b);});
}
function details(){
 const d=$("details");d.replaceChildren();const title=document.createElement("b");title.textContent=state.view==="planet"?"Select a region":"Selected planetary reference";d.append(title);
 const p=document.createElement("p");
 p.textContent=state.view==="planet"?"Navigation markers show documented site locations, not scientific matches.":state.reference?"Measured reference: "+state.reference.name:"No measured Moon/Mars reference profile is available for this location. Similarity percentages are unavailable.";
 d.append(p);
 if(state.selected){const v=document.createElement("p");v.textContent="Earth location: "+state.selected.name+" ("+fmt(state.selected)+")";d.append(v);
  if(state.selected.features){for(const [key,value] of Object.entries(state.selected.features)){const r=document.createElement("p");r.textContent=key+": "+value.value+" "+value.unit;d.append(r);}}}
}
function paint(){updateHeader();renderList();details();render();}
async function loadPlanet(target){
 const token=++state.token;Object.assign(state,{target,view:"planet",sites:[],earth:[],reference:null,selected:null,angle:-.5,pitch:.18,zoom:1});
 $("location-search").value="";paint();
 try{const data=await request("/exploration/sites?body="+target);if(token!==state.token)return;state.sites=data.sites;paint();}
 catch(e){$("list-label").textContent="Unable to load sites: "+e.message;}
}
async function choose(item){
 if(state.view==="earth"){state.selected=item;state.angle=-rad(item.longitude);state.pitch=rad(item.latitude);paint();return;}
 const token=++state.token;state.view="earth";state.reference=null;state.selected=null;state.earth=[];$("location-search").value="";paint();
 try{
  const [planet,earth]=await Promise.all([request("/science/profiles?body="+state.target+"&limit=200"),request("/science/profiles?body=earth&limit=200")]);
  if(token!==state.token)return;
  state.reference=planet.profiles.find(p=>Math.abs(p.latitude-item.latitude)<.1&&Math.abs(p.longitude-item.longitude)<.1)||null;
  state.earth=earth.profiles;paint();
 }catch(e){$("list-label").textContent="Unable to load profiles: "+e.message;}
}
$("moon-tab").addEventListener("click",()=>loadPlanet("moon"));$("mars-tab").addEventListener("click",()=>loadPlanet("mars"));
$("back-button").addEventListener("click",()=>loadPlanet(state.target));$("reset-button").addEventListener("click",()=>{state.angle=-.5;state.pitch=.18;state.zoom=1;render()});
$("location-search").addEventListener("input",renderList);
canvas.addEventListener("pointerdown",e=>{state.drag={x:e.clientX,y:e.clientY,moved:false};canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener("pointermove",e=>{if(!state.drag)return;let dx=e.clientX-state.drag.x,dy=e.clientY-state.drag.y;if(Math.abs(dx)+Math.abs(dy)>3)state.drag.moved=true;state.angle+=dx*.007;state.pitch=Math.max(-1.3,Math.min(1.3,state.pitch+dy*.007));state.drag.x=e.clientX;state.drag.y=e.clientY;render();});
canvas.addEventListener("pointerup",e=>{if(!state.drag)return;const moved=state.drag.moved;state.drag=null;if(moved)return;const rect=canvas.getBoundingClientRect();const x=(e.clientX-rect.left)/rect.width*canvas.width,y=(e.clientY-rect.top)/rect.height*canvas.height;const hit=(state.hits||[]).find(p=>Math.hypot(p.x-x,p.y-y)<15);if(hit)choose(hit.loc)});
canvas.addEventListener("wheel",e=>{e.preventDefault();state.zoom=Math.max(.65,Math.min(1.2,state.zoom-e.deltaY*.0004));render()},{passive:false});
loadPlanet("moon");