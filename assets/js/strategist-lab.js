/* Offline-first research controls. All displayed inputs are embedded snapshots. */
"use strict";
(() => {
  const node = document.getElementById("lab-data");
  if (!node) return;
  const data = JSON.parse(node.textContent);
  const pct = (x, d=2) => (100*x).toFixed(d)+"%";
  const usd = x => new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(x);
  if (data.project === "execution") {
    const venue = document.getElementById("venue-filter");
    const period = document.getElementById("period-filter");
    function draw() {
      const rows = data.rows.filter(r => (venue.value === "All" || r.venue === venue.value) &&
        (period.value === "all" || (period.value === "train" && r.date <= data.train_end) ||
        (period.value === "validation" && r.date > data.train_end && r.date <= data.validation_end) ||
        (period.value === "test" && r.date > data.validation_end)));
      const count = rows.reduce((a,r)=>a+r.orders,0);
      const mean = key => rows.reduce((a,r)=>a+r[key]*r.orders,0)/count;
      const alerts = rows.filter(r=>r.alert).length;
      document.getElementById("exec-residual").textContent=mean("residual_bps").toFixed(2)+" bps";
      document.getElementById("exec-latency").textContent=mean("latency_ms").toFixed(1)+" ms";
      document.getElementById("exec-alerts").textContent=String(alerts);
      document.getElementById("exec-live").textContent=`${venue.value === "All" ? "All venues" : venue.value} · ${count.toLocaleString()} filled orders · ${rows.length} venue-days. Positive values mean higher execution costs than the estimate.`;
      const grouped = new Map();
      rows.forEach(r=>{const x=grouped.get(r.date)||{sum:0,n:0};x.sum+=r.residual_bps*r.orders;x.n+=r.orders;grouped.set(r.date,x);});
      const points=[...grouped].map(([date,v])=>({date,y:v.sum/v.n}));
      const min=Math.min(-.25,...points.map(p=>p.y)),max=Math.max(.5,...points.map(p=>p.y));
      const width=920,height=260,left=58,right=20,top=20,bottom=38;
      const x=i=>left+i*(width-left-right)/Math.max(1,points.length-1);
      const y=v=>height-bottom-(v-min)/(max-min)*(height-top-bottom);
      const grid=Array.from({length:5},(_,i)=>min+i*(max-min)/4).map(v=>`<line class="grid" x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}"/><text x="${left-10}" y="${y(v)+4}" text-anchor="end">${v.toFixed(1)}</text>`).join("");
      const path=points.map((p,i)=>(i?"L":"M")+x(i).toFixed(2)+","+y(p.y).toFixed(2)).join(" ");
      document.getElementById("execution-chart").innerHTML=`<title>Extra execution cost by day (basis points)</title>${grid}<line class="zero" x1="${left}" x2="${width-right}" y1="${y(0)}" y2="${y(0)}"/><path class="line" d="${path}"/>`+
        points.map((p,i)=>`<circle cx="${x(i)}" cy="${y(p.y)}" r="3" fill="#234d70"><title>${p.date}: ${p.y.toFixed(2)} bps</title></circle>`).join("")+
        `<text x="${left}" y="${height-8}">${points[0].date}</text><text x="${width-right}" y="${height-8}" text-anchor="end">${points[points.length-1].date}</text><text x="${left}" y="12">Extra cost (bps)</text>`;
    }
    venue.addEventListener("change",draw);period.addEventListener("change",draw);draw();
  }
  if (data.project === "portfolio") {
    const vol=document.getElementById("vol-multiplier"),corr=document.getElementById("correlation-blend"),lev=document.getElementById("leverage"),allocation=document.getElementById("allocation-filter");
    const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
    function draw() {
      const v=Number(vol.value)/100,c=Number(corr.value)/100,l=Number(lev.value)/100;
      const w=data.snapshot_weights[allocation.value];
      const s=data.covariance_daily.map((row,i)=>Math.sqrt(row[i]));
      const matrix=data.covariance_daily.map((row,i)=>row.map((value,j)=>((1-c)*value+c*s[i]*s[j])*v*v));
      const marginal=matrix.map(row=>dot(row,w));
      const daily=Math.sqrt(dot(w,marginal));
      const annual=daily*Math.sqrt(252)*l;
      const oneDayVar=2.3263478740408408*daily*l*data.nav_usd;
      document.getElementById("risk-vol").textContent=pct(annual);
      document.getElementById("risk-var").textContent=usd(oneDayVar);
      document.getElementById("risk-budget").textContent=usd(data.nav_usd*l);
      document.getElementById("vol-value").textContent=v.toFixed(2)+"×";
      document.getElementById("corr-value").textContent=pct(c,0);
      document.getElementById("leverage-value").textContent=l.toFixed(2)+"×";
      document.getElementById("risk-live").textContent=`As of ${data.as_of}. The estimate assumes a normal bell-shaped return distribution and no expected daily gain. Correlation is moved ${pct(c,0)} of the way towards all six portfolios moving perfectly together. Losses can exceed the displayed threshold.`;
      document.getElementById("risk-table-body").innerHTML=data.book_names.map((name,i)=>{
        const rc=w[i]*marginal[i]/daily*Math.sqrt(252)*l;
        return `<tr><td>${name}</td><td>${pct(w[i],1)}</td><td>${(100*rc).toFixed(2)} pp<div class="lab-bar" style="width:${Math.min(100,Math.abs(rc/annual)*100)}%"></div></td></tr>`;
      }).join("");
    }
    [vol,corr,lev].forEach(el=>el.addEventListener("input",draw));allocation.addEventListener("change",draw);draw();
  }
})();
