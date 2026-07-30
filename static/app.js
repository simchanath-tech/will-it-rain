"use strict";

const $ = id => document.getElementById(id);
const region = $("region");
const destinationSearch = $("destinationSearch");
const destinationMatches = $("destinationMatches");
const searchDestination = $("searchDestination");
const earliestDate = $("earliestDate");
const latestReturn = $("latestReturn");
const tripLength = $("tripLength");
const weekendField = $("weekendField");
const weekendPreference = $("weekendPreference");
const weekendNote = $("weekendNote");
const priority = $("priority");
const planButton = $("planButton");
const loading = $("loading");
const errorBox = $("error");
const resultsSection = $("resultsSection");
const recommendations = $("recommendations");
const resultSummary = $("resultSummary");
const dailySection = $("dailySection");
const dailyTitle = $("dailyTitle");
const dailyCards = $("dailyCards");

let destinationResults = [];
let markers = [];
let latestRecommendations = [];

const map = L.map("map").setView([25, 0], 2);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

function iso(d){
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
const today = new Date();
const earliest = new Date(today); earliest.setDate(earliest.getDate()+30);
const latest = new Date(today); latest.setDate(latest.getDate()+90);
earliestDate.value = iso(earliest);
earliestDate.min = iso(today);
latestReturn.value = iso(latest);
latestReturn.min = iso(today);
const maxDate = new Date(today); maxDate.setDate(maxDate.getDate()+210);
earliestDate.max = iso(maxDate); latestReturn.max = iso(maxDate);

function clearError(){errorBox.classList.add("hidden");}
function showError(message){errorBox.textContent=message;errorBox.classList.remove("hidden");}
async function getJson(url, options){
  const response=await fetch(url, options);
  const data=await response.json();
  if(!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function updateWeekendControl(){
  const days=Number(tripLength.value);
  if(days>=5){
    weekendField.classList.remove("hidden");
    const weekdaysOption=[...weekendPreference.options].find(o=>o.value==="weekdays");
    weekdaysOption.disabled=days>5;
    if(days>5 && weekendPreference.value==="weekdays") weekendPreference.value="include";
    weekendNote.textContent=days>5
      ? "Weekdays Only is unavailable because a continuous trip longer than five days must include a weekend."
      : "Choose whether the five-day trip should include a weekend.";
  }else{
    weekendField.classList.add("hidden");
  }
}
tripLength.addEventListener("change",updateWeekendControl);
updateWeekendControl();

searchDestination.addEventListener("click",async()=>{
  clearError();
  const q=destinationSearch.value.trim();
  if(q.length<2){showError("Enter at least two characters.");return;}
  try{
    const data=await getJson(`/api/geocode?name=${encodeURIComponent(q)}`);
    destinationResults=data.results||[];
    if(!destinationResults.length) throw new Error("No matching destinations found.");
    destinationMatches.innerHTML="";
    destinationResults.forEach((p,i)=>{
      const option=document.createElement("option");
      option.value=i;
      option.textContent=`${p.name}${p.admin1?", "+p.admin1:""}, ${p.country}`;
      destinationMatches.appendChild(option);
    });
    destinationMatches.classList.remove("hidden");
    const p=destinationResults[0];
    map.setView([p.latitude,p.longitude],8);
  }catch(error){showError(error.message);}
});

destinationMatches.addEventListener("change",()=>{
  const p=destinationResults[Number(destinationMatches.value)];
  if(p) map.setView([p.latitude,p.longitude],8);
});

function clearMarkers(){
  markers.forEach(marker=>marker.remove());
  markers=[];
}
function formatDate(text){
  return new Date(`${text}T12:00:00`).toLocaleDateString("en-US",{month:"short",day:"numeric"});
}
function renderDaily(rec){
  dailyTitle.textContent=`${rec.destination}: ${formatDate(rec.startDate)}–${formatDate(rec.endDate)}`;
  dailyCards.innerHTML="";
  rec.daily.forEach(day=>{
    const div=document.createElement("div");
    div.className="day-card";
    div.innerHTML=`
      <strong>${new Date(`${day.date}T12:00:00`).toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})}</strong>
      <div class="day-temp">${day.high.toFixed(0)}° / ${day.low.toFixed(0)}°F</div>
      <div class="day-precip">${day.significantPrecipProbability}% significant rain or snow</div>`;
    dailyCards.appendChild(div);
  });
  dailySection.classList.remove("hidden");
}
function selectRecommendation(index){
  document.querySelectorAll(".rec-card").forEach((el,i)=>el.classList.toggle("active",i===index));
  const rec=latestRecommendations[index];
  map.setView([rec.latitude,rec.longitude],8);
  markers[index].openPopup();
  renderDaily(rec);
}

function renderResults(data){
  latestRecommendations=data.recommendations;
  recommendations.innerHTML="";
  clearMarkers();
  const bounds=[];
  data.recommendations.forEach((rec,index)=>{
    const card=document.createElement("article");
    card.className="rec-card";
    card.innerHTML=`
      <div class="rank">#${index+1}</div>
      <h3>${rec.destination}</h3>
      <div class="country">${rec.country}</div>
      <div class="score">${rec.score}</div>
      <div class="outlook">${rec.outlook}</div>
      <div class="dates">${formatDate(rec.startDate)}–${formatDate(rec.endDate)} · ${rec.tripDays} days</div>
      <div class="metrics">
        <div class="metric"><strong>${rec.averageHigh.toFixed(0)}°</strong><br>High</div>
        <div class="metric"><strong>${rec.averageLow.toFixed(0)}°</strong><br>Low</div>
        <div class="metric" style="grid-column:1/-1"><strong>${rec.significantPrecipProbability}%</strong><br>Significant rain or snow</div>
      </div>`;
    card.addEventListener("click",()=>selectRecommendation(index));
    recommendations.appendChild(card);

    const marker=L.marker([rec.latitude,rec.longitude]).addTo(map)
      .bindPopup(`<strong>#${index+1} ${rec.destination}</strong><br>${rec.outlook} · Score ${rec.score}`);
    marker.on("click",()=>selectRecommendation(index));
    markers.push(marker);
    bounds.push([rec.latitude,rec.longitude]);
  });
  if(bounds.length) map.fitBounds(bounds,{padding:[35,35]});
  resultSummary.textContent=`Evaluated ${data.evaluatedDestinations} destinations in ${data.region}.`;
  resultsSection.classList.remove("hidden");
  selectRecommendation(0);
}

planButton.addEventListener("click",async()=>{
  clearError();
  resultsSection.classList.add("hidden");
  dailySection.classList.add("hidden");
  planButton.disabled=true;
  loading.textContent="Evaluating destinations and every eligible travel window. The first search may take a few minutes while historical data are cached.";
  loading.classList.remove("hidden");
  try{
    const body={
      region:region.value,
      earliestDate:earliestDate.value,
      latestReturn:latestReturn.value,
      tripDays:Number(tripLength.value),
      weekendPreference:Number(tripLength.value)>=5?weekendPreference.value:"any",
      priority:priority.value
    };
    const data=await getJson("/api/plan",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(body)
    });
    renderResults(data);
  }catch(error){showError(error.message);}
  finally{loading.classList.add("hidden");planButton.disabled=false;}
});
