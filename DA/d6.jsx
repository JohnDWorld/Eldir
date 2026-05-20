// Direction 6 - D1 × D3 mix
// Top: D1's fast-read cockpit (telemetry strip + tight session table).
// Body: D3's tactile cork-board with post-its in Past / Now / Next columns.

// ── cork board bg ─────────────────────────────────────────
const CORK_BG = `
  radial-gradient(circle at 22% 31%, rgba(110,75,40,.18) 1.6px, transparent 1.8px),
  radial-gradient(circle at 71% 12%, rgba(80,55,30,.20) 1.4px, transparent 1.6px),
  radial-gradient(circle at 38% 78%, rgba(120,80,45,.16) 1.8px, transparent 2px),
  radial-gradient(circle at 88% 64%, rgba(90,60,35,.18) 1.4px, transparent 1.6px),
  radial-gradient(circle at 12% 56%, rgba(100,70,40,.15) 1.4px, transparent 1.6px),
  radial-gradient(circle at 60% 40%, rgba(130,90,50,.14) 1.5px, transparent 1.7px),
  linear-gradient(180deg, #C9A674 0%, #B8945E 50%, #AC8852 100%)
`;
function Cork({ children, style, frame=true }) {
  return (
    <div style={{background:CORK_BG,
      backgroundSize:'90px 90px,110px 110px,80px 80px,140px 140px,100px 100px,120px 120px,100% 100%',
      boxShadow: frame ? 'inset 0 0 0 6px #6B4A2C, inset 0 0 0 8px #4A3220, inset 0 0 24px rgba(74,50,32,.35)' : 'none',
      borderRadius:frame?6:0, position:'relative', ...style}}>{children}</div>
  );
}

// ── push-pin ──────────────────────────────────────────────
function Pin({ color='#C13E2E', size=10, style }) {
  return (
    <span style={{position:'absolute',top:-4,left:'50%',transform:'translateX(-50%)',width:size,height:size,
      borderRadius:'50%',
      background:`radial-gradient(circle at 35% 30%, #fff 0 1px, ${color} 1.5px 70%, ${darken(color)} 100%)`,
      boxShadow:'0 1px 2px rgba(0,0,0,.5)',
      ...style}}/>
  );
}
function darken(c) { return c==='#C13E2E'?'#7A1F18':c==='#3A6D9C'?'#1F3F61':c==='#D9A24A'?'#7A5A1A':'#3A2D22'; }

// ── post-it ───────────────────────────────────────────────
const POSTIT_COLORS = {
  done:    { bg:'#F0E6C5', tint:'#E0D2A4', edge:'#8C7A4A' },  // aged cream
  now:     { bg:'#FBE769', tint:'#F2D63A', edge:'#9C7E1B' },  // canary yellow
  next:    { bg:'#C9DEF1', tint:'#A6C4DF', edge:'#3F6789' },  // pale blue
  blocked: { bg:'#F4B5A8', tint:'#E59885', edge:'#A24A36' },  // salmon
  input:   { bg:'#F7C97A', tint:'#E0AB4E', edge:'#9C6F1B' },  // amber
};
function PostIt({ kind='done', tilt=0, pin='#C13E2E', children, w, footer, label, style }) {
  const c = POSTIT_COLORS[kind] || POSTIT_COLORS.done;
  return (
    <div style={{position:'relative',transform:`rotate(${tilt}deg)`,transformOrigin:'top center',
      width:w, ...style}}>
      <Pin color={pin}/>
      <div style={{padding:'12px 11px 10px',
        background:`linear-gradient(180deg, ${c.bg} 0%, ${c.tint} 100%)`,
        boxShadow:'0 8px 14px -4px rgba(40,28,12,.4), 0 1px 0 rgba(255,255,255,.5) inset, 0 -1px 0 rgba(0,0,0,.06) inset',
        borderRadius:'2px 2px 4px 4px',
        // bottom-right curl
        clipPath:'polygon(0 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%)',
        position:'relative'}}>
        {label && <div style={{font:'600 9px/1 var(--font-mono)',letterSpacing:'.1em',color:c.edge,textTransform:'uppercase',marginBottom:6}}>{label}</div>}
        <div style={{font:'500 12px/1.35 var(--font-ui)',color:'#2A1F12',letterSpacing:'-.005em'}}>{children}</div>
        {footer && <div style={{font:'500 10px/1 var(--font-mono)',color:c.edge,marginTop:8,display:'flex',justifyContent:'space-between',alignItems:'center',gap:6}}>{footer}</div>}
      </div>
    </div>
  );
}

// ── shared header bits (D1-flavoured) ─────────────────────
function CockpitHeader({ children }) {
  return (
    <div style={{padding:'10px 16px',display:'flex',alignItems:'center',gap:14,background:'var(--paper)',borderBottom:'1px solid var(--gray-3)'}}>
      {children}
    </div>
  );
}
function MiniTile({ label, value, sub, spark, w }) {
  return (
    <div style={{padding:'6px 10px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:3,minWidth:w}}>
      <div style={{font:'600 9px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)'}}>{label}</div>
      <div style={{font:'700 16px/1.1 var(--font-ui)',marginTop:5,fontVariantNumeric:'tabular-nums'}}>{value}</div>
      {spark
        ? <div style={{marginTop:3}}><Spark w={w-22} h={12} fill="rgba(217,119,87,.14)"/></div>
        : <div style={{font:'400 9px/1 var(--font-mono)',color:'var(--gray)',marginTop:3}}>{sub}</div>}
    </div>
  );
}

// ── Mobile · Home ──────────────────────────────────────────
function D6MobileHome() {
  return (
    <Phone>
      {/* dense header */}
      <div style={{padding:'8px 14px',display:'flex',alignItems:'center',justifyContent:'space-between',borderBottom:'1px solid var(--gray-3)'}}>
        <div style={{font:'700 13px/1 var(--font-mono)',letterSpacing:'.1em'}}>ELDIR<span style={{color:'var(--orange)'}}>·</span>CTL</div>
        <div style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>09:41 · 419k · $1.61</div>
      </div>
      {/* telemetry strip */}
      <div style={{padding:'8px 14px',display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:6,
        borderBottom:'1px solid var(--gray-3)'}}>
        <MiniTile label="LIVE" value="3" sub="thinking · tool"/>
        <MiniTile label="WAIT" value="1" sub="awaits you"/>
        <MiniTile label="SPEND" value="$1.61" sub="$8 cap"/>
      </div>
      {/* cork board takes most space */}
      <Cork style={{margin:'10px 12px 70px',padding:'14px 8px 12px',height:'calc(100% - 230px)',overflow:'hidden'}}>
        {/* column heads */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:4,padding:'0 4px 8px'}}>
          {[
            ['◌ DONE', 4, '#3A2D22'],
            ['◉ NOW',  3, '#7A1F18'],
            ['◍ NEXT', 2, '#1F3F61'],
          ].map(([t,n,c],i)=>(
            <div key={i} style={{padding:'5px 7px',background:'rgba(74,50,32,.85)',borderRadius:3,
              font:'600 9px/1 var(--font-mono)',letterSpacing:'.08em',color:'#F0E6C5',
              display:'flex',justifyContent:'space-between'}}>
              <span>{t}</span><span style={{color:'#E0D2A4'}}>{n}</span>
            </div>
          ))}
        </div>
        {/* post-its */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',columnGap:6,rowGap:14,padding:'0 4px',alignItems:'start'}}>
          {/* DONE */}
          <PostIt kind="done" tilt={-2} pin="#3A6D9C" label="atelier · 09:33" w="100%"
            footer={<><span>32m</span><span>$0.74</span></>}>
            Auth token rotation shipped
          </PostIt>
          {/* NOW */}
          <PostIt kind="now" tilt={1.5} pin="#C13E2E" label="eldir · s1" w="100%"
            footer={<><StatePill s="thinking" textColor="#9C7E1B"/><span>$0.21</span></>}>
            Refactor SSE router
          </PostIt>
          {/* NEXT */}
          <PostIt kind="next" tilt={-1} pin="#3A6D9C" label="kiln · queued" w="100%"
            footer={<><span>-</span><span>0.4</span></>}>
            Cut release notes for v0.4
          </PostIt>
          <PostIt kind="done" tilt={1} pin="#3A2D22" label="lumen · 09:18" w="100%"
            footer={<><span>11m</span><span>$0.09</span></>}>
            Forgejo webhook → push event handler
          </PostIt>
          <PostIt kind="input" tilt={-1.5} pin="#D9A24A" label="lumen · s3" w="100%"
            footer={<><StatePill s="input" textColor="#9C6F1B"/><span>3m</span></>}>
            Tailwind purge - confirm safelist?
          </PostIt>
          <PostIt kind="next" tilt={2} pin="#3A6D9C" label="mire · idea" w="100%">
            Notebook export to MDX
          </PostIt>
          <PostIt kind="done" tilt={-1} pin="#3A2D22" label="eldir · 08:52" w="100%"
            footer={<><span>4m</span><span>$0.03</span></>}>
            Spike: ring-buffer perf bench
          </PostIt>
          <PostIt kind="now" tilt={-1.5} pin="#C13E2E" label="eldir · s2" w="100%"
            footer={<><StatePill s="tool" textColor="#9C7E1B"/><span>2m</span></>}>
            pnpm test --filter=core
          </PostIt>
          <span/>
        </div>
      </Cork>
      {/* bottom tab bar */}
      <div style={{position:'absolute',bottom:0,left:0,right:0,height:56,
        borderTop:'1px solid var(--gray-3)',background:'rgba(251,249,244,.95)',
        display:'flex',padding:'0 8px'}}>
        {[['◉','BOARD',true],['▤','PROJ'],['◈','BUILD'],['☰','MORE']].map(([g,l,a],i)=>(
          <div key={i} className="tab44" style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:3,
            color:a?'var(--orange)':'var(--gray)',font:'600 9px/1 var(--font-mono)',letterSpacing:'.1em'}}>
            <span style={{fontSize:14}}>{g}</span>{l}
          </div>
        ))}
      </div>
    </Phone>
  );
}

// ── Mobile · Session timeline ──────────────────────────────
function D6MobileSession() {
  return (
    <Phone>
      <div style={{padding:'8px 14px',borderBottom:'1px solid var(--gray-3)',display:'flex',alignItems:'center',gap:10}}>
        <span style={{font:'500 16px/1 var(--font-mono)',color:'var(--gray)'}}>‹</span>
        <div style={{flex:1,minWidth:0}}>
          <div style={{font:'700 12px/1 var(--font-mono)',color:'var(--ink)',letterSpacing:'.04em'}}>ELDIR / S1</div>
          <div style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)',marginTop:3,display:'inline-flex',gap:5,alignItems:'center'}}>
            <StateDot s="thinking" size={6}/>thinking · 14:22 · 64k · $0.21
          </div>
        </div>
        <span className="tab44" style={{display:'flex',alignItems:'center',justifyContent:'center',width:32,height:32,
          border:'1px solid var(--gray-3)',borderRadius:3,font:'500 11px/1 var(--font-mono)'}}>⏸</span>
      </div>
      {/* tabs */}
      <div style={{padding:'4px 14px 0',display:'flex',gap:4,borderBottom:'1px solid var(--gray-3)'}}>
        {['BOARD','CHAT','DIFF','SHELL'].map((t,i)=>(
          <div key={t} className="tab44" style={{padding:'8px 8px',
            font:'600 10px/1 var(--font-mono)',letterSpacing:'.06em',
            color:i===0?'var(--ink)':'var(--gray)',
            borderBottom:i===0?'2px solid var(--orange)':'2px solid transparent',marginBottom:-1}}>{t}</div>
        ))}
      </div>
      {/* cork */}
      <Cork style={{margin:'10px 12px',padding:'14px 8px',height:'calc(100% - 165px)',overflow:'hidden'}}>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:4,padding:'0 4px 10px'}}>
          {[['DONE',5],['NOW',1],['NEXT',2]].map(([t,n],i)=>(
            <div key={i} style={{padding:'4px 7px',background:'rgba(74,50,32,.85)',borderRadius:3,
              font:'600 9px/1 var(--font-mono)',letterSpacing:'.08em',color:'#F0E6C5',
              display:'flex',justifyContent:'space-between'}}><span>◌ {t}</span><span style={{color:'#E0D2A4'}}>{n}</span></div>
          ))}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',columnGap:6,rowGap:14,padding:'0 4px',alignItems:'start'}}>
          <PostIt kind="done" tilt={-2} pin="#3A2D22" label="14:09" w="100%">
            Read router.ts
          </PostIt>
          <PostIt kind="now" tilt={1.5} pin="#C13E2E" label="14:22 · running" w="100%"
            footer={<StatePill s="tool" textColor="#9C7E1B"/>}>
            pnpm test --filter=core
          </PostIt>
          <PostIt kind="next" tilt={-1} pin="#3A6D9C" label="queued" w="100%">
            Open PR: feat/sessions
          </PostIt>
          <PostIt kind="done" tilt={1} pin="#3A2D22" label="14:12" w="100%">
            Spotted socketId vs sessionId bug
          </PostIt>
          <span/>
          <PostIt kind="next" tilt={1} pin="#3A6D9C" label="if green" w="100%">
            Smoke-test reconnect on staging
          </PostIt>
          <PostIt kind="done" tilt={-1.5} pin="#3A2D22" label="14:18" w="100%"
            footer={<><span style={{color:'var(--green)'}}>+18</span><span style={{color:'var(--red)'}}>−7</span></>}>
            Edit router.ts: ring buffer
          </PostIt>
          <span/>
          <span/>
          <PostIt kind="done" tilt={2} pin="#3A2D22" label="14:19" w="100%">
            Edit types.ts
          </PostIt>
          <span/><span/>
        </div>
      </Cork>
      {/* composer */}
      <div style={{position:'absolute',bottom:14,left:14,right:14,padding:'8px 12px',
        background:'var(--paper)',border:'1px solid var(--gray-3)',borderRadius:4,
        display:'flex',gap:8,alignItems:'center'}}>
        <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--orange)'}}>›</span>
        <span style={{flex:1,font:'400 12px/1 var(--font-ui)',color:'var(--gray)'}}>Pin a note or /command…</span>
        <span style={{font:'500 9px/1 var(--font-mono)',color:'var(--gray)'}}>⌘↵</span>
      </div>
    </Phone>
  );
}

// ── Desktop · Board ────────────────────────────────────────
function D6DeskHome() {
  return (
    <Desk url="eldir.local/board">
      {/* dense topbar (D1) */}
      <div style={{height:42,borderBottom:'1px solid var(--gray-3)',background:'var(--cream-2)',
        display:'flex',alignItems:'center',padding:'0 16px',gap:14}}>
        <div style={{font:'700 13px/1 var(--font-mono)',letterSpacing:'.1em'}}>ELDIR<span style={{color:'var(--orange)'}}>·</span>CTL</div>
        <div style={{display:'flex',gap:0}}>
          {['BOARD','PROJECTS','BUILDS','SETTINGS'].map((t,i)=>(
            <div key={t} style={{padding:'10px 14px',font:'600 11px/1 var(--font-mono)',letterSpacing:'.06em',
              color:i===0?'var(--ink)':'var(--gray)',
              borderBottom:i===0?'2px solid var(--orange)':'2px solid transparent',marginBottom:-1}}>{t}</div>
          ))}
        </div>
        <div style={{flex:1}}/>
        <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>419k tokens · $1.61 / $8.00 today</span>
        <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>09:41 UTC</span>
        <Avatar size={24}>J</Avatar>
      </div>
      {/* telemetry strip + tight session table */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 360px',height:'calc(100% - 42px)'}}>
        <div style={{display:'flex',flexDirection:'column',borderRight:'1px solid var(--gray-3)'}}>
          {/* tiles row */}
          <div style={{padding:'10px 16px 8px',display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:8,
            borderBottom:'1px solid var(--gray-3)'}}>
            {[
              ['ACTIVE','3','sessions'],
              ['INPUT','1','awaiting you'],
              ['IDLE','2','projects'],
              ['BLOCKED','0','-'],
              ['TOKENS','419k','today',true],
              ['SPEND','$1.61','$8 cap',true],
            ].map(([l,v,s,k],i)=>(
              <div key={i} style={{padding:'7px 9px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:3}}>
                <div style={{font:'600 9px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)'}}>{l}</div>
                <div style={{font:'700 19px/1.1 var(--font-ui)',marginTop:5,fontVariantNumeric:'tabular-nums'}}>{v}</div>
                {k ? <div style={{marginTop:4}}><Spark w={120} h={14} fill="rgba(217,119,87,.12)"/></div>
                   : <div style={{font:'400 9px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>{s}</div>}
              </div>
            ))}
          </div>
          {/* the cork board */}
          <Cork style={{flex:1,padding:'18px 16px 22px',overflow:'hidden'}}>
            {/* column headers */}
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:14,marginBottom:14}}>
              {[
                ['◌  DONE TODAY',     '5 cards · $1.21'],
                ['◉  IN FLIGHT',      '3 cards · $0.40'],
                ['◍  UP NEXT',        '4 cards · queued'],
              ].map(([t,m],i)=>(
                <div key={i} style={{padding:'7px 12px',
                  background:'rgba(58,40,22,.88)',
                  borderRadius:3,
                  display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span style={{font:'700 11px/1 var(--font-mono)',letterSpacing:'.1em',color:'#F0E6C5'}}>{t}</span>
                  <span style={{font:'500 10px/1 var(--font-mono)',color:'#C9B27A'}}>{m}</span>
                </div>
              ))}
            </div>
            {/* columns */}
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:14,alignItems:'start'}}>
              {/* DONE */}
              <div style={{display:'flex',flexDirection:'column',gap:18}}>
                <PostIt kind="done" tilt={-1.5} pin="#3A6D9C" label="atelier · 09:33"
                  footer={<><span>32m · 132k</span><span>$0.74</span></>}>
                  Auth token rotation - shipped to staging, manual smoke ok
                </PostIt>
                <PostIt kind="done" tilt={1} pin="#3A2D22" label="lumen · 09:18"
                  footer={<><span>11m</span><span>$0.09</span></>}>
                  Forgejo webhook → push event handler
                </PostIt>
                <PostIt kind="done" tilt={-1} pin="#3A2D22" label="eldir · 08:52"
                  footer={<><span>4m</span><span>$0.03</span></>}>
                  Spike: ring-buffer perf bench (256 vs 1024)
                </PostIt>
                <PostIt kind="done" tilt={1.5} pin="#3A6D9C" label="kiln · 08:11"
                  footer={<><span>2m</span><span>-</span></>}>
                  Bump tsup to 8.4
                </PostIt>
                <PostIt kind="done" tilt={-2} pin="#3A2D22" label="eldir · 07:46"
                  footer={<><span>9m</span><span>$0.12</span></>}>
                  Doc: SSE reconnect contract
                </PostIt>
              </div>
              {/* NOW */}
              <div style={{display:'flex',flexDirection:'column',gap:18}}>
                <PostIt kind="now" tilt={1.5} pin="#C13E2E" label="eldir · s1 · 14:22"
                  footer={<><StatePill s="thinking" textColor="#9C7E1B"/><span>$0.21</span></>}>
                  Refactor session router for SSE reconnect - switching to per-session ring buffer
                </PostIt>
                <PostIt kind="now" tilt={-1} pin="#C13E2E" label="eldir · s2 · 14:21"
                  footer={<><StatePill s="tool" textColor="#9C7E1B"/><span>$0.04</span></>}>
                  pnpm test --filter=core (running)
                </PostIt>
                <PostIt kind="input" tilt={2} pin="#D9A24A" label="lumen · s3 · 09:38"
                  footer={<><StatePill s="input" textColor="#9C6F1B"/><span>$0.21</span></>}>
                  Tailwind purge - confirm safelist? 3 candidates flagged
                </PostIt>
              </div>
              {/* NEXT */}
              <div style={{display:'flex',flexDirection:'column',gap:18}}>
                <PostIt kind="next" tilt={-1} pin="#3A6D9C" label="kiln · queued"
                  footer={<><span>v0.4</span><span>-</span></>}>
                  Cut release notes for v0.4 (changelog draft ready)
                </PostIt>
                <PostIt kind="next" tilt={1.5} pin="#3A6D9C" label="atelier · queued"
                  footer={<><span>after auth</span><span>-</span></>}>
                  Add OAuth flow for Forgejo
                </PostIt>
                <PostIt kind="next" tilt={-1.5} pin="#3A6D9C" label="eldir · idea">
                  Per-session token caps + soft warnings
                </PostIt>
                <PostIt kind="next" tilt={1} pin="#3A6D9C" label="mire · idea">
                  Notebook export to MDX
                </PostIt>
              </div>
            </div>
          </Cork>
        </div>
        {/* right rail: dense session table + log stream (D1) */}
        <div style={{display:'flex',flexDirection:'column'}}>
          <div style={{padding:'10px 14px 8px',font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',display:'flex',justifyContent:'space-between',borderBottom:'1px solid var(--gray-3)'}}>
            <span>SESSIONS · 4</span><span style={{color:'var(--orange)'}}>+ NEW</span>
          </div>
          <div style={{padding:'2px 0',borderBottom:'1px solid var(--gray-3)'}}>
            {SESSIONS.map(s=>(
              <div key={s.id} style={{padding:'8px 14px',display:'grid',gridTemplateColumns:'10px 1fr auto',gap:8,
                background:s.id==='s1'?'var(--cream)':'transparent',borderLeft:s.id==='s1'?'2px solid var(--orange)':'2px solid transparent',
                borderBottom:'1px dotted var(--gray-3)'}}>
                <StateDot s={s.state} size={7}/>
                <div style={{minWidth:0}}>
                  <div style={{font:'600 11px/1 var(--font-mono)',color:'var(--ink)'}}>{s.proj}/{s.id}</div>
                  <div style={{font:'400 10px/1.3 var(--font-ui)',color:'var(--gray)',marginTop:3,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary}</div>
                </div>
                <div style={{textAlign:'right',font:'500 9px/1.4 var(--font-mono)',color:'var(--gray)'}}>
                  {s.dur}<br/><span style={{color:'var(--ink)'}}>{s.cost}</span>
                </div>
              </div>
            ))}
          </div>
          {/* log stream */}
          <div style={{padding:'10px 14px 6px',font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)'}}>STREAM</div>
          <div style={{flex:1,padding:'4px 12px 14px',background:'var(--ink)',color:'var(--cream)',
            font:'400 10.5px/1.55 var(--font-mono)',margin:'0 14px 14px',borderRadius:3,overflow:'hidden'}}>
            <div style={{color:'var(--gray-2)',padding:'6px 0 4px'}}>// all sessions</div>
            {[
              ['09:41:07','s1','thinking','switching to per-session ring buffer'],
              ['09:41:02','s1','tool','edit_file router.ts +18 −7'],
              ['09:40:58','s2','tool','run_bash pnpm test --filter=core'],
              ['09:40:45','s3','input','awaiting safelist confirmation'],
              ['09:40:14','s1','tool','read_file router.ts'],
              ['09:39:50','s1','thinking','investigating buffer keys'],
              ['09:33:11','s4','idle','session ended (rotation done)'],
              ['09:18:02','-', 'event','forgejo webhook · push'],
            ].map((e,i)=>(
              <div key={i} style={{display:'flex',gap:7,padding:'1px 0',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                <span style={{color:'#9c948a'}}>{e[0]}</span>
                <span style={{color:e[1]==='-'?'#9c948a':'var(--orange)',width:18}}>{e[1]}</span>
                <span style={{color:STATES[e[2]]?STATES[e[2]].color:'#9c948a',width:60}}>{STATES[e[2]]?STATES[e[2]].label:e[2]}</span>
                <span style={{color:'var(--cream)',flex:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{e[3]}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Desk>
  );
}

// ── Desktop · Session ──────────────────────────────────────
function D6DeskSession() {
  return (
    <Desk url="eldir.local/board/eldir/s1">
      {/* dense topbar */}
      <div style={{height:42,borderBottom:'1px solid var(--gray-3)',background:'var(--cream-2)',
        display:'flex',alignItems:'center',padding:'0 16px',gap:14}}>
        <span style={{font:'600 11px/1 var(--font-mono)',color:'var(--gray)'}}>‹ BOARD /</span>
        <span style={{font:'700 12px/1 var(--font-mono)',color:'var(--ink)',letterSpacing:'.04em'}}>ELDIR / S1</span>
        <StatePill s="thinking"/>
        <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>feat/sessions · 14:22 · 64k · $0.21</span>
        <div style={{flex:1}}/>
        {['Pause','Diff','Shell','⋯'].map(b=>(
          <span key={b} className="tab44" style={{padding:'5px 10px',font:'500 11px/1 var(--font-mono)',color:'var(--ink)',
            border:'1px solid var(--gray-3)',background:'var(--paper)',borderRadius:3,minWidth:'auto',minHeight:'auto'}}>{b}</span>
        ))}
      </div>
      {/* split: cork timeline | chat | meta */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 280px',height:'calc(100% - 42px)'}}>
        {/* cork session timeline */}
        <Cork frame={false} style={{borderRight:'1px solid var(--gray-3)',padding:'14px 14px 14px',overflow:'hidden',
          boxShadow:'inset 4px 0 8px rgba(74,50,32,.15)'}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:8,marginBottom:12}}>
            {[['DONE',5],['NOW',2],['NEXT',3]].map(([t,n],i)=>(
              <div key={i} style={{padding:'5px 9px',background:'rgba(58,40,22,.88)',borderRadius:3,
                font:'700 10px/1 var(--font-mono)',letterSpacing:'.1em',color:'#F0E6C5',
                display:'flex',justifyContent:'space-between'}}>◌ {t}<span style={{color:'#C9B27A'}}>{n}</span></div>
            ))}
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10,alignItems:'start'}}>
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              <PostIt kind="done" tilt={-1.5} pin="#3A2D22" label="14:09">Read router.ts</PostIt>
              <PostIt kind="done" tilt={1} pin="#3A2D22" label="14:12">Spotted socketId vs sessionId</PostIt>
              <PostIt kind="done" tilt={-1} pin="#3A2D22" label="14:18"
                footer={<><span style={{color:'#3F8C3D'}}>+18</span><span style={{color:'#A24A36'}}>−7</span></>}>
                Edit router.ts: ring buffer
              </PostIt>
              <PostIt kind="done" tilt={1.5} pin="#3A2D22" label="14:19">Edit types.ts: SessionId</PostIt>
              <PostIt kind="done" tilt={-1} pin="#3A2D22" label="14:20">Read router.test.ts</PostIt>
            </div>
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              <PostIt kind="now" tilt={1.5} pin="#C13E2E" label="14:22 · running"
                footer={<><StatePill s="tool" textColor="#9C7E1B"/><span>2m</span></>}>
                pnpm test --filter=core
              </PostIt>
              <PostIt kind="now" tilt={-1} pin="#C13E2E" label="claude · thinking"
                footer={<StatePill s="thinking" textColor="#9C7E1B"/>}>
                "verify subscriber set survives close/reopen"
              </PostIt>
            </div>
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              <PostIt kind="next" tilt={-1} pin="#3A6D9C" label="if green">Smoke-test reconnect on staging</PostIt>
              <PostIt kind="next" tilt={1.5} pin="#3A6D9C" label="queued">Open PR: feat/sessions</PostIt>
              <PostIt kind="next" tilt={-1.5} pin="#3A6D9C" label="follow-up">Update SSE reconnect doc</PostIt>
            </div>
          </div>
        </Cork>
        {/* chat */}
        <div style={{display:'flex',flexDirection:'column',borderRight:'1px solid var(--gray-3)',background:'var(--paper)'}}>
          <div style={{padding:'8px 14px',borderBottom:'1px solid var(--gray-3)',font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)'}}>CONVERSATION</div>
          <div style={{flex:1,padding:14,overflow:'auto',display:'flex',flexDirection:'column',gap:10}}>
            <UserBubble>The session router drops SSE messages when the client reconnects mid-stream. Investigate.</UserBubble>
            <ClaudeBubble>Reading the router to see how it buffers messages between connections.</ClaudeBubble>
            <ToolRow name="read_file" arg="src/server/sessions/router.ts" meta="142 lines"/>
            <ClaudeBubble>The buffer is keyed on socket id, not session id - switching to a per-session ring buffer.</ClaudeBubble>
            <ToolRow name="edit_file" arg="router.ts" meta="+18 −7"/>
            <ToolRow name="run_bash" arg="pnpm test --filter=core" meta="running…" running/>
          </div>
          <div style={{padding:'8px 14px 12px',borderTop:'1px solid var(--gray-3)'}}>
            <div style={{display:'flex',gap:8,alignItems:'center',background:'var(--cream)',
              border:'1px solid var(--gray-3)',borderRadius:3,padding:'7px 10px'}}>
              <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--orange)'}}>›</span>
              <span style={{flex:1,font:'400 12px/1 var(--font-ui)',color:'var(--gray)'}}>Reply, /command, or @file…</span>
              <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>⌘↵</span>
            </div>
          </div>
        </div>
        {/* meta + diff */}
        <div style={{padding:'10px 14px',background:'var(--paper)',overflow:'auto'}}>
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',marginBottom:8}}>SESSION META</div>
          <KV6 k="project" v="eldir"/>
          <KV6 k="branch" v="feat/sessions"/>
          <KV6 k="provider" v="forgejo"/>
          <KV6 k="model" v="sonnet 4.5"/>
          <KV6 k="started" v="14:09"/>
          <KV6 k="auth" v="pro"/>
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',margin:'14px 0 6px'}}>DIFF · router.ts <span style={{float:'right',color:'var(--gray)'}}>+18 −7</span></div>
          <div style={{border:'1px solid var(--gray-3)',borderRadius:3,background:'var(--cream)',
            font:'400 10.5px/1.5 var(--font-mono)',padding:'4px 0'}}>
            {DIFF_LINES.map((l,i)=>(
              <div key={i} style={{padding:'0 8px',display:'flex',gap:6,
                background:l.t==='+'?'rgba(92,138,90,.10)':l.t==='-'?'rgba(184,84,71,.10)':'transparent',
                color:l.t==='h'?'var(--gray)':'var(--ink)'}}>
                <span style={{width:8,color:l.t==='+'?'var(--green)':l.t==='-'?'var(--red)':'var(--gray-2)'}}>{l.t==='+'?'+':l.t==='-'?'−':' '}</span>
                <span style={{whiteSpace:'pre',overflow:'hidden',textOverflow:'ellipsis'}}>{l.s}</span>
              </div>
            ))}
          </div>
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',margin:'14px 0 6px'}}>SPEND</div>
          <div style={{padding:8,background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:3}}>
            <Spark w={230} h={28} fill="rgba(217,119,87,.14)"/>
            <div style={{display:'flex',justifyContent:'space-between',marginTop:5,font:'500 10px/1 var(--font-mono)'}}>
              <span style={{color:'var(--ink)'}}>$0.21</span><span style={{color:'var(--gray)'}}>cap $2.00</span>
            </div>
          </div>
        </div>
      </div>
    </Desk>
  );
}

function KV6({ k, v }) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',padding:'3px 0',
      font:'400 11px/1.4 var(--font-mono)',borderBottom:'1px dotted var(--gray-3)'}}>
      <span style={{color:'var(--gray)'}}>{k}</span><span style={{color:'var(--ink)'}}>{v}</span>
    </div>
  );
}

Object.assign(window, { D6MobileHome, D6MobileSession, D6DeskHome, D6DeskSession });
