// Direction 2 — "Focus mode"
// Linear / Things 3. One session, fullscreen. Swipe / cmd+K to switch.

function D2MobileHome() {
  return (
    <Phone>
      <div style={{padding:'18px 20px 10px'}}>
        <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.04em'}}>Tuesday · April 9</div>
        <div style={{font:'600 26px/1.1 var(--font-ui)',color:'var(--ink)',marginTop:4,letterSpacing:'-.02em'}}>Eldir</div>
      </div>
      {/* attention */}
      <div style={{margin:'8px 16px 18px',padding:14,background:'var(--ink)',color:'var(--cream)',borderRadius:14,position:'relative'}}>
        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
          <StateDot s="input" size={9}/>
          <span style={{font:'500 10px/1 var(--font-ui)',letterSpacing:'.06em',textTransform:'uppercase',color:'var(--gold)'}}>Awaiting you</span>
        </div>
        <div style={{font:'500 15px/1.35 var(--font-ui)',letterSpacing:'-.01em'}}>lumen-web · Tailwind purge — confirm safelist?</div>
        <div style={{font:'400 12px/1 var(--font-ui)',color:'var(--gray-2)',marginTop:8}}>3 minutes ago · $0.21</div>
      </div>
      {/* working on */}
      <div style={{padding:'0 20px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>In flight</div>
      <div style={{padding:'8px 12px 0',display:'flex',flexDirection:'column',gap:2}}>
        {SESSIONS.filter(s=>s.state!=='input').map(s=>(
          <div key={s.id} style={{padding:'14px 8px',display:'flex',gap:12,alignItems:'center',borderRadius:8}}>
            <StateDot s={s.state} size={9}/>
            <div style={{flex:1,minWidth:0}}>
              <div style={{font:'500 14px/1.25 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em'}}>{s.summary}</div>
              <div style={{font:'400 11px/1 var(--font-ui)',color:'var(--gray)',marginTop:4,display:'flex',gap:6,alignItems:'center'}}>
                <span>{s.proj}</span><span>·</span><span>{s.dur}</span><span>·</span><span>{s.cost}</span>
              </div>
            </div>
            <div style={{font:'500 14px/1 var(--font-ui)',color:'var(--gray-2)'}}>›</div>
          </div>
        ))}
      </div>
      {/* projects */}
      <div style={{padding:'18px 20px 6px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Projects</div>
      <div style={{padding:'0 12px'}}>
        {PROJECTS.slice(0,3).map(p=>(
          <div key={p.id} style={{padding:'12px 8px',display:'flex',alignItems:'center',gap:12}}>
            <span style={{width:30,height:30,borderRadius:8,background:'var(--cream-2)',
              display:'inline-flex',alignItems:'center',justifyContent:'center',font:'600 12px/1 var(--font-mono)',color:'var(--ink)'}}>{p.name[0]}</span>
            <div style={{flex:1,minWidth:0}}>
              <div style={{font:'500 14px/1.2 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em',display:'flex',gap:6,alignItems:'center'}}>{p.name}<GitMark kind={p.pv} size={11} color="var(--gray-2)"/></div>
              <div style={{font:'400 11px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>{p.branch}</div>
            </div>
            {p.sessions>0 && <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--orange)'}}>{p.sessions} live</span>}
          </div>
        ))}
      </div>
      {/* FAB */}
      <div style={{position:'absolute',bottom:24,right:24,width:54,height:54,borderRadius:27,
        background:'var(--orange)',display:'flex',alignItems:'center',justifyContent:'center',
        boxShadow:'0 8px 24px rgba(217,119,87,.45)',color:'#fff',font:'400 26px/1 var(--font-ui)'}}>+</div>
    </Phone>
  );
}

function D2MobileSession() {
  return (
    <Phone>
      <div style={{padding:'12px 20px',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <span style={{font:'500 16px/1 var(--font-ui)',color:'var(--gray)'}}>‹</span>
        <div style={{display:'flex',alignItems:'center',gap:6,font:'500 12px/1 var(--font-ui)',color:'var(--ink)'}}>
          eldir / router-fix
        </div>
        <span style={{font:'500 16px/1 var(--font-ui)',color:'var(--gray)'}}>⋯</span>
      </div>
      {/* swipe rail */}
      <div style={{padding:'4px 20px 12px',display:'flex',gap:5,justifyContent:'center'}}>
        {[1,1,1,1].map((_,i)=>(
          <span key={i} style={{width:i===0?22:5,height:5,borderRadius:3,
            background:i===0?'var(--orange)':'var(--gray-3)'}}/>
        ))}
      </div>
      {/* status hero */}
      <div style={{padding:'0 20px',display:'flex',alignItems:'center',gap:10,marginBottom:12}}>
        <StateDot s="thinking" size={10}/>
        <span style={{font:'500 11px/1 var(--font-ui)',color:'var(--orange)',textTransform:'uppercase',letterSpacing:'.08em'}}>Thinking…</span>
        <span style={{flex:1}}/>
        <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>14:22 · $0.21</span>
      </div>
      <div style={{flex:1,padding:'0 20px 100px',overflow:'hidden',display:'flex',flexDirection:'column',gap:14}}>
        <div>
          <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.06em',textTransform:'uppercase',marginBottom:6}}>You</div>
          <div style={{font:'400 14px/1.45 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.005em'}}>The session router drops SSE messages when the client reconnects mid-stream.</div>
        </div>
        <div>
          <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:6}}>
            <Avatar bg="var(--orange)" fg="#fff" size={16}>C</Avatar>
            <span style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.06em',textTransform:'uppercase'}}>Claude</span>
          </div>
          <div style={{font:'400 14px/1.45 var(--font-ui)',color:'var(--ink)'}}>The buffer is keyed on socket id, not session id — that's why a reconnect loses everything. Switching to a per-session ring buffer.</div>
        </div>
        <ToolStrip name="edit_file" arg="src/server/sessions/router.ts" meta="+18 −7"/>
        <ToolStrip name="run_bash" arg="pnpm test --filter=core" meta="running" running/>
      </div>
      {/* input */}
      <div style={{position:'absolute',bottom:24,left:20,right:20,
        background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:14,padding:'12px 16px',
        display:'flex',alignItems:'center',gap:10,boxShadow:'0 4px 12px rgba(0,0,0,.04)'}}>
        <span style={{font:'400 14px/1 var(--font-ui)',color:'var(--gray)',flex:1}}>Reply…</span>
        <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>⌘K</span>
      </div>
    </Phone>
  );
}

function ToolStrip({ name, arg, meta, running }) {
  return (
    <div style={{padding:'10px 12px',background:'var(--cream)',borderRadius:10,
      display:'flex',gap:10,alignItems:'center'}}>
      <span style={{width:28,height:28,borderRadius:8,background:'var(--cream-2)',
        display:'inline-flex',alignItems:'center',justifyContent:'center',
        font:'500 13px/1 var(--font-mono)',color:running?'var(--orange)':'var(--gold)'}}>
        {running?'◌':'◇'}
      </span>
      <div style={{flex:1,minWidth:0}}>
        <div style={{font:'500 12px/1.2 var(--font-mono)',color:'var(--ink)'}}>{name}</div>
        <div style={{font:'400 11px/1 var(--font-mono)',color:'var(--gray)',marginTop:3,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{arg}</div>
      </div>
      <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>{meta}</span>
    </div>
  );
}

function D2DeskHome() {
  return (
    <Desk url="eldir.local">
      <div style={{display:'grid',gridTemplateColumns:'240px 1fr',height:'100%'}}>
        {/* sidebar */}
        <div style={{borderRight:'1px solid var(--gray-3)',background:'var(--cream)',padding:'18px 0'}}>
          <div style={{padding:'0 20px 18px',display:'flex',alignItems:'center',gap:8}}>
            <span style={{width:24,height:24,borderRadius:6,background:'var(--orange)',
              display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#fff',font:'700 13px/1 var(--font-ui)'}}>E</span>
            <span style={{font:'600 14px/1 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em'}}>Eldir</span>
          </div>
          <NavRow icon="◐" label="Inbox" badge="1" active/>
          <NavRow icon="◇" label="In flight" badge="3"/>
          <NavRow icon="□" label="Projects"/>
          <NavRow icon="◑" label="Costs"/>
          <NavRow icon="⚙" label="Settings"/>
          <div style={{padding:'18px 20px 8px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Pinned</div>
          {PROJECTS.slice(0,3).map(p=>(
            <NavRow key={p.id} icon={<GitMark kind={p.pv} size={11} color="var(--gray)"/>} label={p.name} badge={p.sessions||''}/>
          ))}
          <div style={{position:'absolute',bottom:14,left:14,right:14,padding:'10px 12px',
            border:'1px dashed var(--gray-3)',borderRadius:8,
            font:'500 11px/1.3 var(--font-mono)',color:'var(--gray)'}}>
            Press <span style={{color:'var(--ink)'}}>⌘K</span> to jump anywhere
          </div>
        </div>
        {/* main */}
        <div style={{padding:'40px 60px',overflow:'auto'}}>
          <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.04em'}}>Tuesday · April 9</div>
          <div style={{font:'600 36px/1.05 var(--font-ui)',letterSpacing:'-.025em',marginTop:6}}>Inbox</div>
          <div style={{font:'400 14px/1.4 var(--font-ui)',color:'var(--gray)',marginTop:8}}>One thing waiting on you. Three sessions in flight.</div>

          <div style={{marginTop:32,padding:24,background:'var(--ink)',color:'var(--cream)',borderRadius:14,
            display:'flex',gap:18,alignItems:'flex-start'}}>
            <div style={{paddingTop:4}}><StateDot s="input" size={11}/></div>
            <div style={{flex:1}}>
              <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gold)',letterSpacing:'.06em',textTransform:'uppercase'}}>Awaiting your input</div>
              <div style={{font:'500 22px/1.3 var(--font-ui)',marginTop:8,letterSpacing:'-.015em'}}>lumen-web · Tailwind purge — confirm safelist?</div>
              <div style={{font:'400 13px/1.5 var(--font-ui)',color:'var(--gray-2)',marginTop:8,maxWidth:520}}>
                Claude needs you to verify which classes should survive purge. Three candidates flagged in <span style={{color:'var(--cream)',font:'500 12px/1 var(--font-mono)'}}>tailwind.safelist.json</span>.
              </div>
              <div style={{display:'flex',gap:8,marginTop:18}}>
                <Btn dark>Open session</Btn>
                <Btn>Snooze 1h</Btn>
              </div>
            </div>
            <div style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray-2)'}}>3m ago · $0.21</div>
          </div>

          <div style={{marginTop:32,font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>In flight</div>
          <div style={{marginTop:12,display:'flex',flexDirection:'column'}}>
            {SESSIONS.filter(s=>s.state!=='input').map(s=>(
              <div key={s.id} style={{padding:'18px 12px',display:'flex',gap:14,alignItems:'center',borderBottom:'1px solid var(--gray-3)'}}>
                <StateDot s={s.state} size={9}/>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{font:'500 15px/1.3 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em'}}>{s.summary}</div>
                  <div style={{font:'400 12px/1 var(--font-ui)',color:'var(--gray)',marginTop:5,display:'flex',gap:8,alignItems:'center'}}>
                    <span>{s.proj}</span><span>·</span><StatePill s={s.state}/><span>·</span><span>{s.dur}</span>
                  </div>
                </div>
                <span style={{font:'500 12px/1 var(--font-mono)',color:'var(--gray)'}}>{s.cost}</span>
                <span style={{font:'500 14px/1 var(--font-ui)',color:'var(--gray-2)'}}>›</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      {/* fake cmd-K palette */}
      <div style={{position:'absolute',top:80,left:'50%',transform:'translateX(-50%)',width:520,
        background:'var(--paper)',border:'1px solid var(--gray-3)',borderRadius:12,
        boxShadow:'0 24px 60px -12px rgba(0,0,0,.25)',overflow:'hidden'}}>
        <div style={{padding:'14px 18px',borderBottom:'1px solid var(--gray-3)',display:'flex',alignItems:'center',gap:10}}>
          <span style={{font:'500 14px/1 var(--font-mono)',color:'var(--orange)'}}>›</span>
          <span style={{font:'400 14px/1 var(--font-ui)',color:'var(--ink)',flex:1}}>session router</span>
          <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)',padding:'3px 6px',background:'var(--cream-2)',borderRadius:3}}>⌘K</span>
        </div>
        <div>
          {[
            ['◇','Refactor session router for SSE reconnect','eldir / s1'],
            ['◌','Run pnpm test --filter=core','eldir / s2'],
            ['◐','Tailwind purge — confirm safelist?','lumen / s3'],
            ['+','New session in eldir','press ↵'],
          ].map((r,i)=>(
            <div key={i} style={{padding:'12px 18px',display:'flex',alignItems:'center',gap:12,
              background:i===0?'var(--cream)':'transparent'}}>
              <span style={{width:22,height:22,borderRadius:5,background:'var(--cream-2)',display:'inline-flex',alignItems:'center',justifyContent:'center',font:'500 12px/1 var(--font-mono)',color:'var(--orange)'}}>{r[0]}</span>
              <div style={{flex:1}}>
                <div style={{font:'500 13px/1.2 var(--font-ui)',color:'var(--ink)'}}>{r[1]}</div>
                <div style={{font:'400 11px/1 var(--font-mono)',color:'var(--gray)',marginTop:3}}>{r[2]}</div>
              </div>
              {i===0 && <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>↵</span>}
            </div>
          ))}
        </div>
      </div>
    </Desk>
  );
}

function NavRow({ icon, label, badge, active }) {
  return (
    <div style={{padding:'7px 16px',margin:'1px 8px',display:'flex',alignItems:'center',gap:10,borderRadius:6,
      background:active?'var(--cream-2)':'transparent',
      color:active?'var(--ink)':'var(--ink-2)',
      font:'500 13px/1 var(--font-ui)'}}>
      <span style={{width:14,display:'inline-flex',alignItems:'center',justifyContent:'center',color:active?'var(--orange)':'var(--gray)'}}>{icon}</span>
      <span style={{flex:1}}>{label}</span>
      {badge && <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)',padding:'2px 6px',background:'var(--cream)',borderRadius:3}}>{badge}</span>}
    </div>
  );
}
function Btn({ children, dark }) {
  return <div style={{padding:'7px 12px',font:'500 12px/1 var(--font-ui)',
    color:dark?'var(--ink)':'var(--cream)',background:dark?'var(--cream)':'transparent',
    border:dark?'none':'1px solid var(--gray)',borderRadius:6}}>{children}</div>;
}

function D2DeskSession() {
  return (
    <Desk url="eldir.local/s1">
      <div style={{display:'grid',gridTemplateColumns:'240px 1fr 360px',height:'100%'}}>
        <div style={{borderRight:'1px solid var(--gray-3)',background:'var(--cream)',padding:'18px 0'}}>
          <div style={{padding:'0 20px 18px',display:'flex',alignItems:'center',gap:8}}>
            <span style={{width:24,height:24,borderRadius:6,background:'var(--orange)',
              display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#fff',font:'700 13px/1 var(--font-ui)'}}>E</span>
            <span style={{font:'600 14px/1 var(--font-ui)'}}>Eldir</span>
          </div>
          <div style={{padding:'4px 20px 6px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Sessions · 4</div>
          {SESSIONS.map(s=>(
            <div key={s.id} style={{padding:'10px 16px',margin:'1px 8px',borderRadius:6,
              background:s.id==='s1'?'var(--cream-2)':'transparent',
              display:'flex',alignItems:'flex-start',gap:10}}>
              <StateDot s={s.state} size={8}/>
              <div style={{flex:1,minWidth:0}}>
                <div style={{font:'500 13px/1.25 var(--font-ui)',color:'var(--ink)',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary}</div>
                <div style={{font:'400 10px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>{s.proj} · {s.dur}</div>
              </div>
            </div>
          ))}
        </div>
        {/* center */}
        <div style={{display:'flex',flexDirection:'column'}}>
          <div style={{padding:'24px 60px 18px',borderBottom:'1px solid var(--gray-3)'}}>
            <div style={{display:'flex',alignItems:'center',gap:10}}>
              <StateDot s="thinking" size={10}/>
              <span style={{font:'500 11px/1 var(--font-ui)',color:'var(--orange)',textTransform:'uppercase',letterSpacing:'.08em'}}>Thinking…</span>
              <span style={{flex:1}}/>
              <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>eldir / feat-sessions · 14:22 · $0.21</span>
            </div>
            <div style={{font:'600 24px/1.25 var(--font-ui)',letterSpacing:'-.02em',marginTop:10}}>Refactor session router for SSE reconnect</div>
          </div>
          <div style={{flex:1,padding:'24px 60px',overflow:'auto',display:'flex',flexDirection:'column',gap:22}}>
            <Block label="You">The session router drops SSE messages when the client reconnects mid-stream. Investigate.</Block>
            <Block claude label="Claude">Reading the router to see how it buffers messages between connections.</Block>
            <ToolStrip name="read_file" arg="src/server/sessions/router.ts" meta="142 lines"/>
            <Block claude label="Claude">The buffer is keyed on socket id, not session id — that's why a reconnect loses everything. Switching to a per-session ring buffer.</Block>
            <ToolStrip name="edit_file" arg="src/server/sessions/router.ts" meta="+18 −7"/>
            <ToolStrip name="run_bash" arg="pnpm test --filter=core" meta="running" running/>
          </div>
          <div style={{padding:'14px 60px 24px',borderTop:'1px solid var(--gray-3)'}}>
            <div style={{padding:'14px 18px',background:'var(--cream)',borderRadius:12,display:'flex',alignItems:'center',gap:12}}>
              <span style={{font:'500 14px/1 var(--font-ui)',color:'var(--gray)',flex:1}}>Reply…</span>
              <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>⌘↵ to send</span>
            </div>
          </div>
        </div>
        {/* right detail */}
        <div style={{borderLeft:'1px solid var(--gray-3)',padding:'24px 24px',overflow:'auto'}}>
          <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Diff · router.ts</div>
          <div style={{marginTop:10,border:'1px solid var(--gray-3)',borderRadius:8,overflow:'hidden'}}>
            <div style={{padding:'8px 12px',background:'var(--cream-2)',font:'500 11px/1 var(--font-mono)',color:'var(--ink)',display:'flex',justifyContent:'space-between'}}>
              <span>router.ts</span><span style={{color:'var(--gray)'}}>+18 −7</span>
            </div>
            <div style={{font:'400 11px/1.6 var(--font-mono)',padding:'6px 0'}}>
              {DIFF_LINES.map((l,i)=>(
                <div key={i} style={{padding:'0 12px',display:'flex',gap:10,
                  background:l.t==='+'?'rgba(92,138,90,.10)':l.t==='-'?'rgba(184,84,71,.10)':'transparent',
                  color:l.t==='h'?'var(--gray)':'var(--ink)'}}>
                  <span style={{width:10,color:l.t==='+'?'var(--green)':l.t==='-'?'var(--red)':'var(--gray-2)'}}>{l.t==='+'?'+':l.t==='-'?'−':' '}</span>
                  <span style={{whiteSpace:'pre',overflow:'hidden',textOverflow:'ellipsis'}}>{l.s}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{marginTop:20,font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Session</div>
          <div style={{marginTop:10}}>
            <KV k="branch" v="feat/sessions"/>
            <KV k="provider" v="forgejo"/>
            <KV k="model" v="claude-sonnet-4.5"/>
            <KV k="tokens" v="64,210"/>
            <KV k="cost" v="$0.21"/>
          </div>
        </div>
      </div>
    </Desk>
  );
}

function Block({ children, claude, label }) {
  return (
    <div>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
        {claude && <Avatar bg="var(--orange)" fg="#fff" size={20}>C</Avatar>}
        <span style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.06em',textTransform:'uppercase'}}>{label}</span>
      </div>
      <div style={{font:'400 15px/1.55 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.005em'}}>{children}</div>
    </div>
  );
}

Object.assign(window, { D2MobileHome, D2MobileSession, D2DeskHome, D2DeskSession });
