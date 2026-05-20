// Direction 1 - "Mission Control"
// Cockpit / NASA control room. Dense panels, tabbed mobile, multi-pane desktop.

function D1MobileHome() {
  return (
    <Phone>
      <div style={{padding:'10px 16px 0',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <div style={{font:'700 13px/1 var(--font-mono)',letterSpacing:'.1em',color:'var(--ink)'}}>ELDIR<span style={{color:'var(--orange)'}}>·</span>CTL</div>
        <div style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>09:41:22 UTC</div>
      </div>
      <div style={{padding:'8px 16px 6px',display:'flex',gap:6,borderBottom:'1px solid var(--gray-3)'}}>
        {['Overview','Projects','Sessions','Logs'].map((t,i)=>(
          <div key={t} className="tab44" style={{flex:1,textAlign:'center',padding:'10px 4px',
            font:'600 11px/1 var(--font-ui)',letterSpacing:'.04em',textTransform:'uppercase',
            color:i===0?'var(--ink)':'var(--gray)',
            borderBottom:i===0?'2px solid var(--orange)':'2px solid transparent',marginBottom:-1}}>{t}</div>
        ))}
      </div>
      {/* Telemetry strip */}
      <div style={{padding:'10px 16px',display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:8,
        borderBottom:'1px solid var(--gray-3)'}}>
        <Tile label="ACTIVE" value="4" sub="sessions" />
        <Tile label="TOKENS" value="419k" sub="today" spark/>
        <Tile label="SPEND" value="$1.61" sub="$8/d cap" />
      </div>
      {/* Sessions */}
      <div style={{padding:'10px 16px',font:'600 10px/1 var(--font-ui)',letterSpacing:'.08em',color:'var(--gray)',display:'flex',justifyContent:'space-between'}}>
        <span>LIVE SESSIONS · 4</span><span style={{color:'var(--orange)'}}>+ NEW</span>
      </div>
      <div style={{padding:'0 16px',display:'flex',flexDirection:'column',gap:6}}>
        {SESSIONS.map(s=>(
          <div key={s.id} style={{padding:'10px 12px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:4,
            display:'flex',gap:10,alignItems:'center'}}>
            <StateDot s={s.state} size={9}/>
            <div style={{flex:1,minWidth:0}}>
              <div style={{display:'flex',gap:6,alignItems:'baseline'}}>
                <span style={{font:'600 12px/1 var(--font-mono)',color:'var(--ink)'}}>{s.proj}</span>
                <span style={{font:'500 9px/1 var(--font-mono)',color:'var(--gray)'}}>{s.dur}</span>
              </div>
              <div style={{font:'400 11px/1.25 var(--font-ui)',color:'var(--gray)',marginTop:3,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{s.summary}</div>
            </div>
            <div style={{textAlign:'right',font:'500 9px/1.3 var(--font-mono)',color:'var(--gray)'}}>
              {s.tokens}<br/><span style={{color:'var(--ink)'}}>{s.cost}</span>
            </div>
          </div>
        ))}
      </div>
      {/* bottom tab bar (system) */}
      <div style={{position:'absolute',bottom:0,left:0,right:0,height:56,
        borderTop:'1px solid var(--gray-3)',background:'rgba(251,249,244,.92)',
        display:'flex',alignItems:'stretch',padding:'0 8px'}}>
        {[['◉','OPS',true],['▤','PROJ'],['◈','BUILD'],['☰','MORE']].map(([g,l,a],i)=>(
          <div key={i} className="tab44" style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:3,
            color:a?'var(--orange)':'var(--gray)',font:'600 9px/1 var(--font-mono)',letterSpacing:'.1em'}}>
            <span style={{fontSize:14,lineHeight:1}}>{g}</span>{l}
          </div>
        ))}
      </div>
    </Phone>
  );
}

function Tile({ label, value, sub, spark }) {
  return (
    <div style={{padding:'8px 10px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:3}}>
      <div style={{font:'600 9px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)'}}>{label}</div>
      <div style={{font:'700 18px/1.1 var(--font-ui)',color:'var(--ink)',marginTop:6,fontVariantNumeric:'tabular-nums'}}>{value}</div>
      {spark
        ? <div style={{marginTop:4}}><Spark w={70} h={14}/></div>
        : <div style={{font:'400 9px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>{sub}</div>}
    </div>
  );
}

function D1MobileSession() {
  return (
    <Phone>
      <div style={{padding:'10px 14px',borderBottom:'1px solid var(--gray-3)',display:'flex',alignItems:'center',gap:10}}>
        <div style={{font:'600 16px/1 var(--font-ui)',color:'var(--gray)'}}>‹</div>
        <div style={{flex:1,minWidth:0}}>
          <div style={{font:'600 13px/1 var(--font-mono)',color:'var(--ink)'}}>eldir / s1</div>
          <div style={{display:'flex',gap:6,alignItems:'center',marginTop:3}}>
            <StatePill s="thinking"/>
            <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>· 14:22 · 64k · $0.21</span>
          </div>
        </div>
        <div className="tab44" style={{display:'flex',alignItems:'center',justifyContent:'center',
          width:34,height:34,border:'1px solid var(--gray-3)',borderRadius:3,
          font:'500 11px/1 var(--font-mono)',color:'var(--ink)'}}>⏸</div>
      </div>
      {/* segmented panels (mission control feel) */}
      <div style={{padding:'8px 14px 0',display:'flex',gap:4}}>
        {['CHAT','DIFF','SHELL','META'].map((t,i)=>(
          <div key={t} className="tab44" style={{padding:'8px 10px',
            font:'600 10px/1 var(--font-mono)',letterSpacing:'.06em',
            color:i===0?'var(--ink)':'var(--gray)',
            borderBottom:i===0?'2px solid var(--orange)':'2px solid transparent'}}>{t}</div>
        ))}
      </div>
      {/* chat */}
      <div style={{padding:'10px 14px 90px',display:'flex',flexDirection:'column',gap:10,
        height:'calc(100% - 200px)',overflow:'hidden'}}>
        <UserBubble>The session router drops SSE messages when the client reconnects mid-stream.</UserBubble>
        <ClaudeBubble>Reading the router to see how it buffers messages between connections.</ClaudeBubble>
        <ToolRow name="read_file" arg="src/server/sessions/router.ts" meta="142 lines"/>
        <ClaudeBubble>The buffer is keyed on socket id, not session id - switching to a per-session ring buffer.</ClaudeBubble>
        <ToolRow name="edit_file" arg="router.ts" meta="+18 −7"/>
      </div>
      {/* input */}
      <div style={{position:'absolute',bottom:56,left:0,right:0,padding:'8px 12px',
        background:'var(--paper)',borderTop:'1px solid var(--gray-3)'}}>
        <div style={{display:'flex',gap:8,alignItems:'center',background:'var(--cream)',
          border:'1px solid var(--gray-3)',borderRadius:3,padding:'8px 10px'}}>
          <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--orange)'}}>›</span>
          <span style={{flex:1,font:'400 12px/1 var(--font-ui)',color:'var(--gray)'}}>Reply or /command…</span>
          <span style={{font:'500 9px/1 var(--font-mono)',color:'var(--gray)'}}>⌘↵</span>
        </div>
      </div>
      {/* bottom tab bar */}
      <div style={{position:'absolute',bottom:0,left:0,right:0,height:56,
        borderTop:'1px solid var(--gray-3)',background:'rgba(251,249,244,.92)',
        display:'flex',padding:'0 8px'}}>
        {[['◉','OPS'],['▤','PROJ'],['◈','BUILD',true],['☰','MORE']].map(([g,l,a],i)=>(
          <div key={i} className="tab44" style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:3,
            color:a?'var(--orange)':'var(--gray)',font:'600 9px/1 var(--font-mono)',letterSpacing:'.1em'}}>
            <span style={{fontSize:14}}>{g}</span>{l}
          </div>
        ))}
      </div>
    </Phone>
  );
}

function UserBubble({ children }) {
  return <div style={{alignSelf:'flex-end',maxWidth:'85%',padding:'8px 11px',
    background:'var(--ink)',color:'var(--cream)',borderRadius:'10px 10px 2px 10px',
    font:'400 12px/1.4 var(--font-ui)'}}>{children}</div>;
}
function ClaudeBubble({ children }) {
  return (
    <div style={{maxWidth:'90%',display:'flex',gap:8}}>
      <Avatar bg="var(--orange)" fg="#fff" size={20}>C</Avatar>
      <div style={{padding:'8px 11px',background:'var(--cream)',border:'1px solid var(--gray-3)',
        borderRadius:'2px 10px 10px 10px',font:'400 12px/1.4 var(--font-ui)',color:'var(--ink)'}}>{children}</div>
    </div>
  );
}
function ToolRow({ name, arg, meta, running }) {
  return (
    <div style={{display:'flex',gap:6,alignItems:'center',padding:'5px 9px',
      border:'1px dashed var(--gray-2)',borderRadius:3,
      font:'500 10px/1.3 var(--font-mono)',color:'var(--gray)'}}>
      <span style={{color:running?'var(--orange)':'var(--gold)'}}>◇</span>
      <span style={{color:'var(--ink)'}}>{name}</span>
      <span style={{opacity:.7,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>({arg})</span>
      <span style={{marginLeft:'auto',color:'var(--gray)'}}>{meta}</span>
    </div>
  );
}

// ── Desktop: 4-pane mission control ─────────────────────────
function D1DeskHome() {
  return (
    <Desk url="eldir.local/ops">
      {/* Topbar */}
      <div style={{height:42,borderBottom:'1px solid var(--gray-3)',background:'var(--cream-2)',
        display:'flex',alignItems:'center',padding:'0 16px',gap:14}}>
        <div style={{font:'700 13px/1 var(--font-mono)',letterSpacing:'.1em'}}>ELDIR<span style={{color:'var(--orange)'}}>·</span>CTL</div>
        <div style={{display:'flex',gap:2}}>
          {['OPS','PROJECTS','BUILDS','SETTINGS'].map((t,i)=>(
            <div key={t} style={{padding:'10px 14px',font:'600 11px/1 var(--font-mono)',letterSpacing:'.06em',
              color:i===0?'var(--ink)':'var(--gray)',
              borderBottom:i===0?'2px solid var(--orange)':'2px solid transparent',marginBottom:-1}}>{t}</div>
          ))}
        </div>
        <div style={{flex:1}}/>
        <div style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>419k tokens · $1.61 / $8.00 today</div>
        <Avatar size={24}>J</Avatar>
      </div>
      {/* Telemetry strip */}
      <div style={{padding:'10px 16px',display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:10,
        borderBottom:'1px solid var(--gray-3)'}}>
        {[
          ['ACTIVE',  '4',     'sessions'],
          ['IDLE',    '2',     'projects'],
          ['INPUT',   '1',     'awaiting you'],
          ['BLOCKED', '0',     '-'],
          ['TOKENS',  '419k',  'today',  true],
          ['SPEND',   '$1.61', '$8 cap', true],
        ].map(([l,v,s,k],i)=>(
          <div key={i} style={{padding:'8px 10px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:3}}>
            <div style={{font:'600 9px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)'}}>{l}</div>
            <div style={{font:'700 22px/1.1 var(--font-ui)',marginTop:6,fontVariantNumeric:'tabular-nums'}}>{v}</div>
            {k ? <div style={{marginTop:4}}><Spark w={120} h={16} fill="rgba(217,119,87,.12)"/></div>
               : <div style={{font:'400 9px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>{s}</div>}
          </div>
        ))}
      </div>
      {/* main 3-col grid */}
      <div style={{display:'grid',gridTemplateColumns:'260px 1fr 320px',height:'calc(100% - 116px)'}}>
        {/* projects rail */}
        <div style={{borderRight:'1px solid var(--gray-3)',padding:'10px 0',overflow:'auto'}}>
          <div style={{padding:'4px 14px 8px',font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',display:'flex',justifyContent:'space-between'}}>
            <span>PROJECTS · {PROJECTS.length}</span><span style={{color:'var(--orange)'}}>+</span>
          </div>
          {PROJECTS.map(p=>(
            <div key={p.id} style={{padding:'9px 14px',display:'flex',gap:8,alignItems:'center',
              background:p.id==='eldir'?'var(--cream)':'transparent',borderLeft:p.id==='eldir'?'2px solid var(--orange)':'2px solid transparent'}}>
              <GitMark kind={p.pv} size={11} color="var(--gray)"/>
              <div style={{flex:1,minWidth:0}}>
                <div style={{font:'600 12px/1 var(--font-mono)',color:'var(--ink)'}}>{p.name}</div>
                <div style={{font:'400 10px/1.2 var(--font-mono)',color:'var(--gray)',marginTop:3,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{p.branch}</div>
              </div>
              <div style={{textAlign:'right'}}>
                {p.sessions>0 && <div style={{display:'inline-flex',gap:3,alignItems:'center',font:'600 10px/1 var(--font-mono)',color:'var(--orange)'}}>{p.sessions}<StateDot s={p.id==='lumen'?'input':'thinking'} size={6}/></div>}
                <div style={{font:'400 9px/1 var(--font-mono)',color:'var(--gray)',marginTop:3}}>{p.last}</div>
              </div>
            </div>
          ))}
        </div>
        {/* sessions grid */}
        <div style={{padding:14,overflow:'auto'}}>
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',marginBottom:10,display:'flex',justifyContent:'space-between'}}>
            <span>LIVE SESSIONS</span><span>FILTER · ALL · ACTIVE · INPUT · BLOCKED</span>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
            {SESSIONS.map(s=>(
              <div key={s.id} style={{padding:12,background:'var(--cream)',border:'1px solid var(--gray-3)',
                borderRadius:3,borderLeft:`3px solid ${STATES[s.state].color}`}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span style={{font:'600 12px/1 var(--font-mono)',color:'var(--ink)'}}>{s.proj} <span style={{color:'var(--gray)'}}>/ {s.id}</span></span>
                  <StatePill s={s.state}/>
                </div>
                <div style={{font:'400 11px/1.4 var(--font-ui)',color:'var(--ink-2)',marginTop:8}}>{s.summary}</div>
                <div style={{display:'flex',gap:10,marginTop:10,font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>
                  <span>⏱ {s.dur}</span><span>◊ {s.tokens}</span><span>{s.cost}</span>
                </div>
              </div>
            ))}
          </div>
          {/* logs panel */}
          <div style={{marginTop:14,padding:12,background:'var(--ink)',color:'var(--cream)',borderRadius:3,
            font:'400 11px/1.5 var(--font-mono)',height:140,overflow:'hidden'}}>
            <div style={{color:'var(--gray-2)',marginBottom:6}}>// stream · all sessions</div>
            <div><span style={{color:'var(--orange)'}}>s1</span> tool_use <span style={{color:'var(--gray-2)'}}>read_file</span> src/server/sessions/router.ts</div>
            <div><span style={{color:'var(--gold)'}}>s2</span> tool_use <span style={{color:'var(--gray-2)'}}>run_bash</span> pnpm test --filter=core</div>
            <div><span style={{color:'var(--amber)'}}>s3</span> awaiting_input <span style={{color:'var(--gray-2)'}}>// safelist confirmation</span></div>
            <div><span style={{color:'var(--orange)'}}>s1</span> claude <span style={{color:'var(--cream)'}}>"switching to per-session ring buffer"</span></div>
            <div><span style={{color:'var(--orange)'}}>s1</span> tool_use <span style={{color:'var(--gray-2)'}}>edit_file</span> +18 −7</div>
          </div>
        </div>
        {/* right rail - events + cost */}
        <div style={{borderLeft:'1px solid var(--gray-3)',padding:'10px 14px',overflow:'auto'}}>
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',marginBottom:8}}>SPEND · 7-DAY</div>
          <div style={{padding:'10px 0',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:3}}>
            <Spark data={[2,4,3,7,5,8,6,11]} w={290} h={56} fill="rgba(217,119,87,.12)"/>
            <div style={{display:'flex',justifyContent:'space-between',padding:'4px 10px',font:'500 9px/1 var(--font-mono)',color:'var(--gray)'}}>
              <span>$0.42 mon</span><span>$1.61 today</span>
            </div>
          </div>
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',margin:'14px 0 8px'}}>EVENTS</div>
          {[
            ['09:41','s1','edit_file router.ts'],
            ['09:39','s3','awaiting input'],
            ['09:36','s2','test passed'],
            ['09:33','s4','session ended'],
            ['09:18','-', 'forgejo webhook · push'],
            ['09:02','s1','session started'],
          ].map((e,i)=>(
            <div key={i} style={{display:'flex',gap:8,padding:'5px 0',font:'400 11px/1.3 var(--font-mono)',
              color:'var(--ink-2)',borderBottom:'1px dotted var(--gray-3)'}}>
              <span style={{color:'var(--gray)'}}>{e[0]}</span>
              <span style={{color:e[1]==='-'?'var(--gray)':'var(--orange)',width:24}}>{e[1]}</span>
              <span style={{flex:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{e[2]}</span>
            </div>
          ))}
        </div>
      </div>
    </Desk>
  );
}

function D1DeskSession() {
  return (
    <Desk url="eldir.local/sessions/s1">
      <div style={{height:42,borderBottom:'1px solid var(--gray-3)',background:'var(--cream-2)',
        display:'flex',alignItems:'center',padding:'0 16px',gap:14}}>
        <span style={{font:'600 11px/1 var(--font-mono)',color:'var(--gray)'}}>‹ OPS / </span>
        <span style={{font:'600 12px/1 var(--font-mono)',color:'var(--ink)'}}>eldir / s1</span>
        <StatePill s="thinking"/>
        <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>14:22 · 64k · $0.21</span>
        <div style={{flex:1}}/>
        {['Pause','Diff','Shell','⋯'].map(b=>(
          <div key={b} style={{padding:'5px 10px',font:'500 11px/1 var(--font-mono)',color:'var(--ink)',
            border:'1px solid var(--gray-3)',background:'var(--paper)',borderRadius:3}}>{b}</div>
        ))}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'200px 1fr 1fr 240px',height:'calc(100% - 42px)'}}>
        {/* sessions rail */}
        <div style={{borderRight:'1px solid var(--gray-3)',padding:'10px 0',overflow:'auto'}}>
          <div style={{padding:'4px 12px 8px',font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)'}}>SESSIONS</div>
          {SESSIONS.map(s=>(
            <div key={s.id} style={{padding:'8px 12px',display:'flex',gap:7,alignItems:'center',
              background:s.id==='s1'?'var(--cream)':'transparent',
              borderLeft:s.id==='s1'?'2px solid var(--orange)':'2px solid transparent'}}>
              <StateDot s={s.state} size={7}/>
              <div style={{flex:1,minWidth:0}}>
                <div style={{font:'600 11px/1 var(--font-mono)',color:'var(--ink)'}}>{s.proj} / {s.id}</div>
                <div style={{font:'400 10px/1.3 var(--font-mono)',color:'var(--gray)',marginTop:2,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary}</div>
              </div>
            </div>
          ))}
        </div>
        {/* chat */}
        <div style={{display:'flex',flexDirection:'column',borderRight:'1px solid var(--gray-3)'}}>
          <div style={{flex:1,padding:14,overflow:'auto',display:'flex',flexDirection:'column',gap:10}}>
            <UserBubble>The session router drops SSE messages when the client reconnects mid-stream. Investigate.</UserBubble>
            <ClaudeBubble>Reading the router to see how it buffers messages between connections.</ClaudeBubble>
            <ToolRow name="read_file" arg="src/server/sessions/router.ts" meta="142 lines"/>
            <ClaudeBubble>The buffer is keyed on socket id, not session id - that's why a reconnect loses everything. Switching to a per-session ring buffer.</ClaudeBubble>
            <ToolRow name="edit_file" arg="router.ts" meta="+18 −7"/>
            <ToolRow name="run_bash" arg="pnpm test --filter=core" meta="running…" running/>
          </div>
          <div style={{padding:'8px 14px 12px',borderTop:'1px solid var(--gray-3)'}}>
            <div style={{display:'flex',gap:8,alignItems:'center',background:'var(--cream)',
              border:'1px solid var(--gray-3)',borderRadius:3,padding:'8px 10px'}}>
              <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--orange)'}}>›</span>
              <span style={{flex:1,font:'400 12px/1 var(--font-ui)',color:'var(--gray)'}}>Reply, /command, or @file…</span>
              <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>⌘↵</span>
            </div>
          </div>
        </div>
        {/* diff */}
        <div style={{display:'flex',flexDirection:'column',background:'var(--paper)'}}>
          <div style={{padding:'8px 12px',borderBottom:'1px solid var(--gray-3)',font:'500 11px/1 var(--font-mono)',color:'var(--ink)',display:'flex',justifyContent:'space-between'}}>
            <span>src/server/sessions/router.ts</span>
            <span style={{color:'var(--gray)'}}>+18 <span style={{color:'var(--green)'}}>●</span> −7 <span style={{color:'var(--red)'}}>●</span></span>
          </div>
          <div style={{flex:1,padding:'8px 0',overflow:'auto',font:'400 11px/1.6 var(--font-mono)'}}>
            {DIFF_LINES.map((l,i)=>(
              <div key={i} style={{padding:'0 12px',display:'flex',gap:10,
                background:l.t==='+'?'rgba(92,138,90,.10)':l.t==='-'?'rgba(184,84,71,.10)':l.t==='h'?'var(--cream-2)':'transparent',
                color:l.t==='h'?'var(--gray)':'var(--ink)'}}>
                <span style={{width:12,color:l.t==='+'?'var(--green)':l.t==='-'?'var(--red)':'var(--gray-2)'}}>{l.t==='+'?'+':l.t==='-'?'−':' '}</span>
                <span style={{whiteSpace:'pre'}}>{l.s}</span>
              </div>
            ))}
          </div>
          <div style={{padding:'6px 12px',borderTop:'1px solid var(--gray-3)',
            background:'var(--ink)',color:'var(--cream)',font:'400 10px/1.4 var(--font-mono)',height:90,overflow:'hidden'}}>
            <div style={{color:'var(--gray-2)'}}>$ pnpm test --filter=core</div>
            <div>core test/router.test.ts ··· running</div>
            <div style={{color:'var(--gold)'}}>  ✓ buffers messages by session id (12ms)</div>
            <div style={{color:'var(--gold)'}}>  ✓ replays missed messages on reconnect (8ms)</div>
            <div style={{color:'var(--gray-2)'}}>  · hold ring at 256 entries…</div>
          </div>
        </div>
        {/* meta */}
        <div style={{borderLeft:'1px solid var(--gray-3)',padding:'10px 14px',overflow:'auto'}}>
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',marginBottom:8}}>SESSION META</div>
          <KV k="project" v="eldir"/>
          <KV k="branch" v="feat/sessions"/>
          <KV k="provider" v="forgejo"/>
          <KV k="started" v="09:27"/>
          <KV k="model" v="claude-sonnet-4.5"/>
          <KV k="auth" v="pro"/>
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',margin:'14px 0 8px'}}>FILES TOUCHED · 3</div>
          {['router.ts','router.test.ts','types.ts'].map(f=>(
            <div key={f} style={{font:'400 11px/1.6 var(--font-mono)',color:'var(--ink)'}}>{f}</div>
          ))}
          <div style={{font:'600 10px/1 var(--font-mono)',letterSpacing:'.08em',color:'var(--gray)',margin:'14px 0 8px'}}>COST</div>
          <div style={{padding:8,background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:3}}>
            <Spark w={210} h={32} fill="rgba(217,119,87,.12)"/>
            <div style={{display:'flex',justifyContent:'space-between',marginTop:6,font:'500 10px/1 var(--font-mono)',color:'var(--ink)'}}>
              <span>$0.21</span><span style={{color:'var(--gray)'}}>cap $2.00</span>
            </div>
          </div>
        </div>
      </div>
    </Desk>
  );
}

function KV({ k, v }) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',padding:'4px 0',
      font:'400 11px/1.4 var(--font-mono)',borderBottom:'1px dotted var(--gray-3)'}}>
      <span style={{color:'var(--gray)'}}>{k}</span><span style={{color:'var(--ink)'}}>{v}</span>
    </div>
  );
}

Object.assign(window, { D1MobileHome, D1MobileSession, D1DeskHome, D1DeskSession });
