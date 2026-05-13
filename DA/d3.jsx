// Direction 3 — "Workshop"
// Atelier metaphor. Pegboard with hanging tools. Warm, organic, tactile.

function Pegboard({ children, style }) {
  // dotted pegboard background
  const dots = `radial-gradient(circle at 12px 12px, rgba(74,55,42,.18) 1.5px, transparent 1.6px)`;
  return (
    <div style={{
      background:`${dots}, linear-gradient(180deg, #E8DDC9 0%, #DDD0B8 100%)`,
      backgroundSize:'24px 24px, 100% 100%',
      ...style
    }}>{children}</div>
  );
}

function ToolHang({ children, label, state, hooked=true, size='m', tilt=0 }) {
  // a "tool" hanging on the pegboard. card with a hook above it.
  const w = size==='l'?160 : size==='s'?108:128;
  return (
    <div style={{position:'relative',transform:`rotate(${tilt}deg)`,
      transformOrigin:'top center',transition:'transform .2s'}}>
      {hooked && <>
        <div style={{position:'absolute',left:'50%',top:-22,width:6,height:24,
          background:'#3A2D22',transform:'translateX(-50%) rotate(35deg)',transformOrigin:'bottom',borderRadius:3}}/>
        <div style={{position:'absolute',left:'50%',top:-3,width:8,height:8,borderRadius:4,
          background:'#3A2D22',transform:'translateX(-50%)'}}/>
      </>}
      <div style={{width:w,padding:'14px 12px 12px',background:'#FBF7EF',
        borderRadius:'4px 4px 8px 8px',
        boxShadow:'0 6px 14px rgba(58,45,34,.18), 0 1px 0 rgba(255,255,255,.6) inset',
        border:'1px solid rgba(58,45,34,.18)'}}>
        {state && <div style={{display:'flex',alignItems:'center',gap:5,marginBottom:6}}>
          <StateDot s={state} size={7}/>
          <span style={{font:'500 9px/1 var(--font-ui)',color:'var(--gray)',textTransform:'uppercase',letterSpacing:'.06em'}}>{STATES[state].label}</span>
        </div>}
        {children}
        <div style={{font:'500 10px/1.2 var(--font-mono)',color:'var(--gray)',marginTop:8,letterSpacing:'-.01em'}}>{label}</div>
      </div>
    </div>
  );
}

function D3MobileHome() {
  return (
    <Phone>
      <div style={{padding:'14px 18px 4px',display:'flex',alignItems:'center',gap:10}}>
        <span style={{width:30,height:30,borderRadius:6,background:'var(--ink)',
          display:'inline-flex',alignItems:'center',justifyContent:'center',color:'var(--orange)',font:'700 14px/1 var(--font-mono)'}}>E</span>
        <div style={{flex:1}}>
          <div style={{font:'700 16px/1 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em'}}>The Workshop</div>
          <div style={{font:'400 11px/1 var(--font-ui)',color:'var(--gray)',marginTop:3}}>Three irons in the fire</div>
        </div>
        <span style={{font:'500 14px/1 var(--font-ui)',color:'var(--ink)'}}>⊕</span>
      </div>
      {/* Pegboard with tools */}
      <Pegboard style={{margin:'12px 14px',padding:'34px 14px 18px',borderRadius:10,
        border:'1px solid rgba(58,45,34,.2)'}}>
        <div style={{font:'500 9px/1 var(--font-ui)',color:'#6a5640',letterSpacing:'.1em',textTransform:'uppercase',marginBottom:16}}>On the bench</div>
        <div style={{display:'flex',flexWrap:'wrap',gap:18,justifyContent:'space-around'}}>
          {SESSIONS.slice(0,3).map((s,i)=>(
            <ToolHang key={s.id} label={`${s.proj} · ${s.dur}`} state={s.state} size="s" tilt={i===1?2:i===2?-3:0}>
              <div style={{font:'500 11px/1.3 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em'}}>{s.summary.slice(0,38)}…</div>
            </ToolHang>
          ))}
        </div>
      </Pegboard>
      {/* Workbench */}
      <div style={{padding:'4px 18px 8px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Projects in shop</div>
      <div style={{padding:'0 14px',display:'flex',flexDirection:'column',gap:6}}>
        {PROJECTS.slice(0,4).map(p=>(
          <div key={p.id} style={{padding:'10px 12px',background:'var(--cream)',border:'1px solid var(--gray-3)',
            borderRadius:6,display:'flex',gap:10,alignItems:'center'}}>
            <span style={{width:32,height:32,borderRadius:5,
              background:`linear-gradient(135deg, ${p.id==='eldir'?'#C9A87C':p.id==='lumen'?'#D9A24A':'#8B8680'} 0%, ${p.id==='eldir'?'#A8865A':p.id==='lumen'?'#B27F2A':'#5C5751'} 100%)`,
              display:'inline-flex',alignItems:'center',justifyContent:'center',
              color:'#FBF9F4',font:'700 13px/1 var(--font-ui)',
              boxShadow:'0 1px 2px rgba(0,0,0,.15) inset'}}>{p.name[0]}</span>
            <div style={{flex:1,minWidth:0}}>
              <div style={{font:'600 13px/1.2 var(--font-ui)',color:'var(--ink)',display:'flex',gap:5,alignItems:'center'}}>{p.name}<GitMark kind={p.pv} size={10} color="var(--gray)"/></div>
              <div style={{font:'400 10px/1.2 var(--font-mono)',color:'var(--gray)',marginTop:3}}>{p.branch} · {p.last}</div>
            </div>
            {p.sessions>0 && <span style={{padding:'3px 7px',background:'var(--orange)',color:'#fff',
              borderRadius:10,font:'600 9px/1 var(--font-mono)'}}>{p.sessions}</span>}
          </div>
        ))}
      </div>
      {/* bottom drawer hint */}
      <div style={{position:'absolute',bottom:0,left:0,right:0,padding:'10px 18px 18px',
        borderTop:'1px solid var(--gray-3)',background:'var(--paper)',display:'flex',gap:10,alignItems:'center'}}>
        <span style={{flex:1,font:'500 12px/1 var(--font-ui)',color:'var(--gray)'}}>⊕ Pull a new tool from the rack</span>
        <span style={{padding:'7px 14px',background:'var(--orange)',color:'#fff',
          borderRadius:6,font:'600 12px/1 var(--font-ui)'}}>New mission</span>
      </div>
    </Phone>
  );
}

function D3MobileSession() {
  return (
    <Phone>
      <div style={{padding:'14px 18px 8px',display:'flex',alignItems:'center',gap:8}}>
        <span style={{font:'500 16px/1 var(--font-ui)',color:'var(--gray)'}}>‹</span>
        <div style={{flex:1}}>
          <div style={{font:'600 14px/1 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em'}}>At the bench</div>
          <div style={{font:'400 11px/1 var(--font-mono)',color:'var(--gray)',marginTop:3}}>eldir / feat-sessions</div>
        </div>
        <span style={{padding:'4px 8px',background:'var(--cream)',borderRadius:4,
          font:'500 10px/1 var(--font-mono)',color:'var(--orange)',display:'flex',alignItems:'center',gap:5}}><StateDot s="thinking"/>thinking</span>
      </div>
      {/* tool rack — small icons of other tools */}
      <Pegboard style={{margin:'8px 14px 12px',padding:'18px 12px 12px',borderRadius:8}}>
        <div style={{font:'500 9px/1 var(--font-ui)',color:'#6a5640',letterSpacing:'.1em',textTransform:'uppercase',marginBottom:10}}>Other tools on the rack</div>
        <div style={{display:'flex',gap:10,overflow:'hidden'}}>
          {SESSIONS.filter(s=>s.id!=='s1').map(s=>(
            <div key={s.id} style={{flex:1,padding:'10px 8px',background:'#FBF7EF',
              borderRadius:'2px 2px 6px 6px',border:'1px solid rgba(58,45,34,.15)'}}>
              <StateDot s={s.state} size={6}/>
              <div style={{font:'500 10px/1.25 var(--font-ui)',color:'var(--ink)',marginTop:5,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.proj}</div>
              <div style={{font:'400 9px/1 var(--font-mono)',color:'var(--gray)',marginTop:3}}>{s.dur}</div>
            </div>
          ))}
        </div>
      </Pegboard>
      {/* the bench — chat */}
      <div style={{padding:'4px 18px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>The bench</div>
      <div style={{flex:1,padding:'10px 18px 100px',display:'flex',flexDirection:'column',gap:12,
        height:'calc(100% - 320px)',overflow:'hidden'}}>
        <UserBubble>The session router drops SSE messages when the client reconnects.</UserBubble>
        <ClaudeBubble>Switching to a per-session ring buffer — that should hold across reconnects.</ClaudeBubble>
        <ToolStrip name="edit_file" arg="router.ts" meta="+18 −7"/>
      </div>
      <div style={{position:'absolute',bottom:18,left:14,right:14,padding:'10px 14px',
        background:'var(--paper)',border:'1px solid var(--gray-3)',borderRadius:8,
        boxShadow:'0 4px 14px rgba(58,45,34,.1)',display:'flex',alignItems:'center',gap:10}}>
        <span style={{font:'500 14px/1 var(--font-ui)',color:'var(--orange)'}}>›</span>
        <span style={{flex:1,font:'400 13px/1 var(--font-ui)',color:'var(--gray)'}}>Hand the tool an instruction…</span>
      </div>
    </Phone>
  );
}

function D3DeskHome() {
  return (
    <Desk url="eldir.local/workshop">
      <div style={{height:'100%',display:'flex',flexDirection:'column'}}>
        {/* topbar */}
        <div style={{padding:'14px 32px',borderBottom:'1px solid var(--gray-3)',
          display:'flex',alignItems:'center',gap:14}}>
          <span style={{width:30,height:30,borderRadius:6,background:'var(--ink)',
            display:'inline-flex',alignItems:'center',justifyContent:'center',color:'var(--orange)',font:'700 14px/1 var(--font-mono)'}}>E</span>
          <div>
            <div style={{font:'700 16px/1 var(--font-ui)',letterSpacing:'-.01em'}}>The Workshop</div>
            <div style={{font:'400 11px/1 var(--font-ui)',color:'var(--gray)',marginTop:3}}>Tuesday morning · three irons in the fire</div>
          </div>
          <div style={{flex:1}}/>
          <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>419k tokens · $1.61 today</span>
          <Avatar size={26}>J</Avatar>
        </div>
        {/* Pegboard hero */}
        <Pegboard style={{flex:1,padding:'52px 36px 28px',position:'relative',overflow:'hidden'}}>
          <div style={{font:'500 11px/1 var(--font-ui)',color:'#6a5640',letterSpacing:'.12em',textTransform:'uppercase',marginBottom:30}}>On the rack</div>
          <div style={{display:'flex',gap:36,flexWrap:'wrap',alignItems:'flex-start'}}>
            {SESSIONS.map((s,i)=>(
              <ToolHang key={s.id} label={`${s.proj} · ${s.dur} · ${s.cost}`} state={s.state} size="m" tilt={[0,3,-2,1][i]}>
                <div style={{font:'500 12px/1.35 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em'}}>{s.summary}</div>
              </ToolHang>
            ))}
            {/* empty hook */}
            <div style={{position:'relative',width:128,padding:'14px 12px',
              background:'transparent',border:'2px dashed rgba(58,45,34,.25)',borderRadius:'4px 4px 8px 8px',
              color:'#6a5640',font:'500 11px/1.4 var(--font-ui)',textAlign:'center',height:120,display:'flex',alignItems:'center',justifyContent:'center'}}>
              <div style={{position:'absolute',left:'50%',top:-22,width:6,height:24,
                background:'#3A2D22',transform:'translateX(-50%) rotate(-25deg)',transformOrigin:'bottom',borderRadius:3}}/>
              <div style={{position:'absolute',left:'50%',top:-3,width:8,height:8,borderRadius:4,
                background:'#3A2D22',transform:'translateX(-50%)'}}/>
              <span>+ Hang a new tool</span>
            </div>
          </div>
        </Pegboard>
        {/* Workbench drawer at bottom — projects */}
        <div style={{padding:'18px 32px',background:'var(--paper)',borderTop:'1px solid var(--gray-3)'}}>
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
            <span style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Workbench · projects in shop</span>
            <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--orange)'}}>+ add repo</span>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:12}}>
            {PROJECTS.map(p=>(
              <div key={p.id} style={{padding:'12px 14px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:6,
                display:'flex',gap:10,alignItems:'flex-start'}}>
                <span style={{width:34,height:34,borderRadius:5,flexShrink:0,
                  background:`linear-gradient(135deg, ${['#C9A87C','#D9A24A','#8B8680','#5C8A5A','#5A7A9A'][PROJECTS.indexOf(p)]} 0%, #5C5751 130%)`,
                  display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#FBF9F4',font:'700 13px/1 var(--font-ui)',
                  boxShadow:'0 1px 2px rgba(0,0,0,.15) inset'}}>{p.name[0]}</span>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{font:'600 13px/1.2 var(--font-ui)',color:'var(--ink)',display:'flex',gap:5,alignItems:'center'}}>{p.name}<GitMark kind={p.pv} size={10} color="var(--gray)"/></div>
                  <div style={{font:'400 10px/1.4 var(--font-mono)',color:'var(--gray)',marginTop:4,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{p.branch}</div>
                  <div style={{display:'flex',gap:6,marginTop:6,alignItems:'center'}}>
                    {p.sessions>0
                      ? <span style={{padding:'2px 6px',background:'var(--orange)',color:'#fff',borderRadius:8,font:'600 9px/1 var(--font-mono)'}}>{p.sessions} live</span>
                      : <span style={{font:'400 9px/1 var(--font-mono)',color:'var(--gray)'}}>{p.last}</span>}
                    <span style={{fontSize:10,color:'var(--gray)'}}>·</span>
                    <span style={{font:'500 9px/1 var(--font-mono)',color:'var(--gray)'}}>{p.cost}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Desk>
  );
}

function D3DeskSession() {
  return (
    <Desk url="eldir.local/workshop/eldir">
      <div style={{display:'grid',gridTemplateColumns:'200px 1fr 320px',height:'100%'}}>
        {/* tool rack on the left */}
        <Pegboard style={{padding:'22px 12px',borderRight:'1px solid var(--gray-3)'}}>
          <div style={{font:'500 9px/1 var(--font-ui)',color:'#6a5640',letterSpacing:'.1em',textTransform:'uppercase',marginBottom:14,paddingLeft:8}}>Tools</div>
          <div style={{display:'flex',flexDirection:'column',gap:24,paddingLeft:8}}>
            {SESSIONS.map((s,i)=>(
              <ToolHang key={s.id} label={`${s.proj} · ${s.dur}`} state={s.state} size="s" tilt={i===0?0:[3,-2,1][i-1]}>
                <div style={{font:'500 10px/1.3 var(--font-ui)',color:'var(--ink)',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary.slice(0,30)}…</div>
              </ToolHang>
            ))}
          </div>
        </Pegboard>
        {/* The bench */}
        <div style={{display:'flex',flexDirection:'column',
          background:'linear-gradient(180deg, #F4EEE0 0%, #ECE3D0 100%)'}}>
          {/* bench-grain top edge */}
          <div style={{height:8,background:'repeating-linear-gradient(90deg, rgba(58,45,34,.18) 0 1px, transparent 1px 14px)'}}/>
          <div style={{padding:'18px 32px 12px',display:'flex',alignItems:'center',gap:12,
            borderBottom:'1px dashed rgba(58,45,34,.2)'}}>
            <span style={{width:36,height:36,borderRadius:8,background:'var(--ink)',
              display:'inline-flex',alignItems:'center',justifyContent:'center',color:'var(--orange)',font:'700 16px/1 var(--font-mono)'}}>E</span>
            <div style={{flex:1}}>
              <div style={{font:'700 17px/1 var(--font-ui)',letterSpacing:'-.015em'}}>eldir / s1</div>
              <div style={{font:'400 11px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>feat/sessions · forgejo · sonnet 4.5</div>
            </div>
            <StatePill s="thinking"/>
            <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>14:22 · $0.21</span>
          </div>
          <div style={{flex:1,padding:'24px 32px',overflow:'auto',display:'flex',flexDirection:'column',gap:18}}>
            <Block label="You">The session router drops SSE messages when the client reconnects mid-stream. Investigate.</Block>
            <Block claude label="Claude">Reading the router to see how it buffers messages between connections.</Block>
            <ToolStrip name="read_file" arg="src/server/sessions/router.ts" meta="142 lines"/>
            <Block claude label="Claude">The buffer is keyed on socket id, not session id. Switching to a per-session ring buffer.</Block>
            <ToolStrip name="edit_file" arg="router.ts" meta="+18 −7"/>
            <ToolStrip name="run_bash" arg="pnpm test --filter=core" meta="running" running/>
          </div>
          <div style={{padding:'12px 32px 22px',borderTop:'1px dashed rgba(58,45,34,.2)'}}>
            <div style={{padding:'12px 16px',background:'var(--paper)',border:'1px solid var(--gray-3)',borderRadius:8,
              boxShadow:'0 1px 0 rgba(255,255,255,.6) inset, 0 4px 14px rgba(58,45,34,.08)',display:'flex',gap:12,alignItems:'center'}}>
              <span style={{font:'500 14px/1 var(--font-ui)',color:'var(--orange)'}}>›</span>
              <span style={{flex:1,font:'400 13px/1 var(--font-ui)',color:'var(--gray)'}}>Hand the tool an instruction… (slash for skills)</span>
              <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>⌘↵</span>
            </div>
          </div>
        </div>
        {/* drawer with diff + cost */}
        <div style={{borderLeft:'1px solid var(--gray-3)',background:'var(--paper)',padding:'22px 22px',overflow:'auto'}}>
          <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase',marginBottom:10}}>Drawer · diff</div>
          <div style={{border:'1px solid var(--gray-3)',borderRadius:8,overflow:'hidden',background:'var(--cream)'}}>
            <div style={{padding:'8px 12px',background:'var(--cream-2)',font:'500 11px/1 var(--font-mono)'}}>router.ts <span style={{color:'var(--gray)',float:'right'}}>+18 −7</span></div>
            <div style={{font:'400 11px/1.6 var(--font-mono)',padding:'6px 0'}}>
              {DIFF_LINES.map((l,i)=>(
                <div key={i} style={{padding:'0 12px',display:'flex',gap:8,
                  background:l.t==='+'?'rgba(92,138,90,.1)':l.t==='-'?'rgba(184,84,71,.1)':'transparent'}}>
                  <span style={{width:10,color:l.t==='+'?'var(--green)':l.t==='-'?'var(--red)':'var(--gray-2)'}}>{l.t==='+'?'+':l.t==='-'?'−':' '}</span>
                  <span style={{whiteSpace:'pre',overflow:'hidden',textOverflow:'ellipsis',color:'var(--ink-2)'}}>{l.s}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase',margin:'18px 0 10px'}}>Ledger</div>
          <div style={{padding:14,background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:8}}>
            <Spark w={250} h={36} fill="rgba(217,119,87,.14)"/>
            <div style={{display:'flex',justifyContent:'space-between',marginTop:8,font:'500 11px/1 var(--font-mono)'}}>
              <span style={{color:'var(--ink)'}}>$0.21 today</span>
              <span style={{color:'var(--gray)'}}>cap $2.00</span>
            </div>
          </div>
        </div>
      </div>
    </Desk>
  );
}

Object.assign(window, { D3MobileHome, D3MobileSession, D3DeskHome, D3DeskSession });
