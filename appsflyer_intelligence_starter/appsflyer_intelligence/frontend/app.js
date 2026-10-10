let token = localStorage.getItem("af_token") || "";
let email = localStorage.getItem("af_email") || "";
let isRegister = false, analysisData = null, charts = {};
const $ = id => document.getElementById(id);
const authView=$("authView"), appView=$("appView");
function authHeaders(){return {"Authorization":"Bearer "+token}}
async function api(path, options={}) {
  const headers = {...(options.headers||{})};
  if(token) headers.Authorization="Bearer "+token;
  const res=await fetch(path,{...options,headers});
  let body={}; try{body=await res.json()}catch{}
  if(!res.ok) throw new Error(body.detail||"Request failed");
  return body;
}
function showAuth(){authView.classList.remove("hidden");appView.classList.add("hidden")}
function showApp(){authView.classList.add("hidden");appView.classList.remove("hidden");$("userEmail").textContent=email;loadAll()}
function authMode(){ $("authTitle").textContent=isRegister?"Create your account":"Welcome back";$("authSubmit").textContent=isRegister?"Create account":"Log in";$("switchText").textContent=isRegister?"Already have an account?":"New to the platform?";$("switchAuth").textContent=isRegister?"Log in":"Create account";$("authError").textContent=""}
$("switchAuth").onclick=()=>{isRegister=!isRegister;authMode()};
$("authForm").onsubmit=async e=>{e.preventDefault();$("authError").textContent="";try{const data=await api(isRegister?"/api/register":"/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:$("email").value,password:$("password").value})});token=data.access_token;email=data.email;localStorage.setItem("af_token",token);localStorage.setItem("af_email",email);showApp()}catch(err){$("authError").textContent=err.message}};
$("logoutBtn").onclick=()=>{token="";email="";localStorage.removeItem("af_token");localStorage.removeItem("af_email");showAuth()};
const pageNames={overview:"Overview dashboard",sources:"Media source analysis",campaigns:"Campaign explorer",events:"Event analysis",data:"Data management"};
function goPage(page){document.querySelectorAll(".page").forEach(p=>p.classList.add("hidden"));$(page+"Page").classList.remove("hidden");document.querySelectorAll(".nav").forEach(n=>n.classList.toggle("active",n.dataset.page===page));$("pageTitle").textContent=pageNames[page];}
document.querySelectorAll("[data-page]").forEach(b=>b.addEventListener("click",()=>goPage(b.dataset.page)));
$("uploadShortcut").onclick=$("emptyUpload").onclick=()=>goPage("data");
$("refreshBtn").onclick=loadAnalysis;
$("datasetSelect").onchange=loadAnalysis;
$("chooseFile").onclick=()=>$("fileInput").click();
$("fileInput").onchange=async e=>{for(const file of e.target.files) await uploadFile(file);e.target.value=""};
const dz=$("dropZone");
dz.addEventListener("dragover",e=>{e.preventDefault();dz.classList.add("drag")});
dz.addEventListener("dragleave",()=>dz.classList.remove("drag"));
dz.addEventListener("drop",async e=>{e.preventDefault();dz.classList.remove("drag");for(const file of e.dataTransfer.files)await uploadFile(file)});
async function uploadFile(file){const status=$("uploadStatus");status.className="upload-status";status.textContent="Uploading and analyzing "+file.name+"…";const fd=new FormData();fd.append("file",file);try{const d=await api("/api/upload",{method:"POST",body:fd});status.className="upload-status status-ok";status.textContent=`Imported ${d.filename}: ${d.rows.toLocaleString()} rows. Detected columns: ${d.columns.join(", ")}.`;await loadAll()}catch(err){status.className="upload-status status-error";status.textContent=file.name+": "+err.message}}
async function loadAll(){try{await loadDatasets();await loadAnalysis()}catch(err){if(err.message.toLowerCase().includes("session")||err.message.toLowerCase().includes("invalid")){showAuth()}else showNotice(err.message)}}
async function loadDatasets(){const data=await api("/api/datasets");const sel=$("datasetSelect"), old=sel.value;sel.innerHTML='<option value="">All datasets</option>'+data.map(d=>`<option value="${esc(d.id)}">${esc(d.filename)} (${d.rows} rows)</option>`).join("");if(data.some(d=>d.id===old))sel.value=old;const list=$("datasetList");list.innerHTML=data.length?data.map(d=>`<div class="dataset-item"><div class="file-icon">▤</div><div class="dataset-info"><b>${esc(d.filename)}</b><small>${Number(d.rows).toLocaleString()} rows · ${new Date(d.created_at+"Z").toLocaleString()}</small></div><button class="delete-btn" data-delete="${esc(d.id)}">Delete</button></div>`).join(""):'<p class="muted">No reports uploaded yet.</p>';list.querySelectorAll("[data-delete]").forEach(b=>b.onclick=async()=>{if(confirm("Delete this dataset and its imported file?")){try{await api("/api/datasets/"+b.dataset.delete,{method:"DELETE"});await loadAll()}catch(e){showNotice(e.message)}}})}
async function loadAnalysis(){try{analysisData=await api("/api/analysis"+($("datasetSelect").value?"?dataset_id="+encodeURIComponent($("datasetSelect").value):""));render()}catch(e){showNotice(e.message)}}
function showNotice(msg){$("notice").textContent=msg;$("notice").classList.remove("hidden")}
function money(v){return v===null||v===undefined||!Number.isFinite(Number(v))?"Unavailable":new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:2,notation:Math.abs(v)>=1e6?"compact":"standard"}).format(v)}
function num(v){return v===null||v===undefined||!Number.isFinite(Number(v))?"Unavailable":new Intl.NumberFormat("en-US",{maximumFractionDigits:2,notation:Math.abs(v)>=1e6?"compact":"standard"}).format(v)}
function pct(v){return v===null||v===undefined||!Number.isFinite(Number(v))?"Unavailable":(v*100).toFixed(2)+"%"}
function metric(v, type){return type==="money"?money(v):type==="pct"?pct(v):num(v)}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function render(){if(!analysisData||analysisData.empty){$("emptyState").classList.remove("hidden");$("dashboardContent").classList.add("hidden");$("emptyState").querySelector("p").innerHTML='Upload an AppsFlyer CSV or Excel report to calculate KPIs and explore campaign performance.<br><a href="/api/demo.csv">Download sample CSV</a> to try the dashboard.';fillTables();return}
$("emptyState").classList.add("hidden");$("dashboardContent").classList.remove("hidden");const k=analysisData.kpis;const cards=[["Total spend",k.spend,"money","$"],["Installs",k.installs,"num","↓"],["Clicks",k.clicks,"num","↗"],["Impressions",k.impressions,"num","◉"],["Conversions",k.conversions,"num","✓"],["Revenue",k.revenue,"money","$"],["Cost per install",k.cpi,"money","⌁"],["ROAS",k.roas,"ratio","↗"]];
$("kpiGrid").innerHTML=cards.map(([label,val,type,icon])=>`<div class="kpi"><div class="kpi-top"><span>${label}</span><span class="kpi-icon">${icon}</span></div><div class="kpi-value">${type==="ratio"?(val==null?"Unavailable":num(val)+"×"):metric(val,type)}</div><div class="kpi-foot">${val==null?"Required source columns may be missing":"Based on selected report filters"}</div></div>`).join("");
drawChart("trendChart",{type:"line",data:{labels:analysisData.daily.map(x=>x.date),datasets:[{label:"Spend",data:analysisData.daily.map(x=>x.spend),borderColor:"#4263eb",backgroundColor:"#4263eb20",fill:true,tension:.3},{label:"Revenue",data:analysisData.daily.map(x=>x.revenue),borderColor:"#19a883",backgroundColor:"#19a88310",fill:false,tension:.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{boxWidth:8,usePointStyle:true,font:{size:10}}}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:7,font:{size:9}}},y:{beginAtZero:true,ticks:{font:{size:9}}}}}});
const top=analysisData.media_sources.slice(0,7);drawChart("sourceChart",{type:"doughnut",data:{labels:top.map(x=>x.name),datasets:[{data:top.map(x=>x.spend||0),backgroundColor:["#4263eb","#19a883","#f0a43a","#8b6cef","#ef6b78","#4dacc4","#9aa4b5"],borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{boxWidth:8,usePointStyle:true,font:{size:10}}}}}});
$("campaignRows").innerHTML=tableRows(analysisData.campaigns.slice(0,8),"campaign");
$("campaignAllRows").innerHTML=tableRows(analysisData.campaigns,"campaignAll");
$("sourceRows").innerHTML=tableRows(analysisData.media_sources,"source");
$("eventRows").innerHTML=analysisData.events.length?analysisData.events.map(x=>`<tr><td>${esc(x.name)}</td><td>${money(x.spend)}</td><td>${num(x.conversions)}</td><td>${money(x.revenue)}</td><td>${num(x.rows)}</td></tr>`).join(""):'<tr><td colspan="5">No event-name column was detected in this report.</td></tr>';
$("qualityText").innerHTML=`<div class="quality-item"><b>${num(analysisData.data_quality.rows)}</b><span>Rows analyzed</span></div><div class="quality-item"><b>${num(analysisData.data_quality.duplicate_rows_exact)}</b><span>Exact duplicate rows</span></div><div class="quality-item"><b>${num(analysisData.data_quality.missing_cells)}</b><span>Missing cells</span></div><div class="quality-item"><b>${analysisData.columns.length}</b><span>Recognized columns</span></div>`;
$("notice").classList.add("hidden");}
function tableRows(rows,kind){if(!rows||!rows.length)return '<tr><td colspan="7">No data available for this view.</td></tr>';return rows.map(x=>`<tr><td>${esc(x.name)}</td><td>${money(x.spend)}</td><td>${num(x.installs)}</td>${kind==="campaignAll"?`<td>${num(x.clicks)}</td><td>${money(x.cpa)}</td>`:`<td>${money(x.cpi)}</td>`}<td>${kind==="campaign"||kind==="campaignAll"?money(x.revenue):num(x.conversions)}</td><td>${x.roas==null?"Unavailable":num(x.roas)+"×"}</td></tr>`).join("")}
function fillTables(){$("campaignRows").innerHTML=$("campaignAllRows").innerHTML=$("sourceRows").innerHTML=$("eventRows").innerHTML='<tr><td colspan="7">Upload a report to see results.</td></tr>'}
function drawChart(id,config){if(charts[id])charts[id].destroy();const el=$(id);if(!el)return;charts[id]=new Chart(el,config)}
$("campaignSearch").oninput=()=>{if(!analysisData||analysisData.empty)return;const q=$("campaignSearch").value.toLowerCase();$("campaignAllRows").innerHTML=tableRows(analysisData.campaigns.filter(x=>x.name.toLowerCase().includes(q)),"campaignAll")};
if(token)showApp();else showAuth();
