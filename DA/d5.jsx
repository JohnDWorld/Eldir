// Direction 5 - "Conversation-led"
// Claude.ai / ChatGPT. The chat IS the interface. Tools render inline in convo.

function D5MobileHome() {
  return (
    <Phone>
      {/* Topbar */}
      <div style={{padding:'12px 16px 8px',display:'flex',alignItems:'center',gap:10,
        borderBottom:'1px solid var(--gray-3)'}}>
        <span style={{font:'500 18px/1 var(--font-ui)',color:'var(--ink)'}}>☰</span>
        <div style={{flex:1,textAlign:'center'}}>
          <div style={{font:'600 13px/1 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em'}}>Eldir</div>
          <div style={{font:'400 10px/1 var(--font-ui)',color:'var(--gray)',marginTop:3}}>4 conversations</div>
        </div>
        <span style={{font:'500 18px/1 var(--font-ui)',color:'var(--orange)'}}>✎</span>
      </div>
      {/* New chat starter */}
      <div style={{margin:'14px 16px 18px',padding:'18px 18px 16px',
        background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:14}}>
        <div style={{display:'flex',gap:10,alignItems:'center',marginBottom:10}}>
          <Avatar bg="var(--orange)" fg="#fff" size={28}>C</Avatar>
          <div>
            <div style={{font:'600 14px/1 var(--font-ui)',letterSpacing:'-.01em'}}>Start a new conversation</div>
            <div style={{font:'400 11px/1 var(--font-ui)',color:'var(--gray)',marginTop:3}}>Pick a project, then say what you want.</div>
          </div>
        </div>
        <div style={{display:'flex',gap:6,flexWrap:'wrap',marginTop:10}}>
          {PROJECTS.slice(0,4).map(p=>(
            <span key={p.id} style={{padding:'5px 10px',background:'var(--paper)',border:'1px solid var(--gray-3)',
              borderRadius:14,font:'500 11px/1 var(--font-mono)',display:'inline-flex',gap:5,alignItems:'center'}}>
              <GitMark kind={p.pv} size={10} color="var(--gray)"/>{p.name}
            </span>
          ))}
        </div>
      </div>
      {/* Recent conversations */}
      <div style={{padding:'0 16px 6px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Conversations</div>
      <div style={{padding:'4px 8px',display:'flex',flexDirection:'column',gap:2}}>
        {SESSIONS.map(s=>(
          <div key={s.id} style={{padding:'12px 10px',display:'flex',gap:11,alignItems:'flex-start',borderRadius:8}}>
            <div style={{paddingTop:3}}>
              <Avatar bg="var(--cream-2)" fg="var(--ink)" size={28}>{s.proj[0].toUpperCase()}</Avatar>
            </div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{display:'flex',alignItems:'center',gap:6}}>
                <span style={{font:'500 13px/1.2 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em',flex:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary}</span>
                <span style={{font:'400 10px/1 var(--font-ui)',color:'var(--gray)'}}>{s.dur}</span>
              </div>
              <div style={{display:'flex',gap:6,alignItems:'center',marginTop:4}}>
                <StatePill s={s.state}/>
                <span style={{font:'400 10px/1 var(--font-ui)',color:'var(--gray)'}}>· {s.proj} · {s.cost}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Phone>
  );
}

function D5MobileSession() {
  return (
    <Phone>
      {/* Header */}
      <div style={{padding:'12px 16px',display:'flex',alignItems:'center',gap:10,borderBottom:'1px solid var(--gray-3)'}}>
        <span style={{font:'500 18px/1 var(--font-ui)',color:'var(--gray)'}}>‹</span>
        <div style={{flex:1,minWidth:0}}>
          <div style={{font:'600 13px/1.2 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>Refactor session router for SSE…</div>
          <div style={{font:'400 11px/1 var(--font-ui)',color:'var(--gray)',marginTop:3,display:'inline-flex',gap:5,alignItems:'center'}}>
            <GitMark kind="fj" size={10} color="var(--gray)"/>eldir · feat/sessions
          </div>
        </div>
        <StateDot s="thinking" size={9}/>
      </div>
      {/* convo */}
      <div style={{flex:1,padding:'14px 16px 100px',overflow:'hidden',display:'flex',flexDirection:'column',gap:14,
        height:'calc(100% - 156px)'}}>
        <C5User>The session router drops SSE messages when the client reconnects mid-stream. Investigate.</C5User>
        <C5Claude>
          <div>Reading the router to see how it buffers messages between connections.</div>
          <C5InlineTool icon="📄" name="read_file" arg="src/server/sessions/router.ts"/>
          <div style={{marginTop:8}}>The buffer is keyed on socket id, not session id - that's why a reconnect loses everything. Switching to a per-session ring buffer.</div>
          <C5InlineDiff/>
          <C5InlineTool icon="▶" name="run_bash" arg="pnpm test --filter=core" running/>
        </C5Claude>
        <div style={{display:'flex',gap:8,alignItems:'center'}}>
          <span style={{padding:'4px 10px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:14,font:'500 11px/1 var(--font-ui)',color:'var(--ink)'}}>↻ Continue</span>
          <span style={{padding:'4px 10px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:14,font:'500 11px/1 var(--font-ui)',color:'var(--ink)'}}>⎘ Copy diff</span>
        </div>
      </div>
      {/* composer */}
      <div style={{position:'absolute',bottom:14,left:14,right:14,padding:'10px 14px',
        background:'var(--paper)',border:'1px solid var(--gray-3)',borderRadius:18,
        boxShadow:'0 4px 14px rgba(0,0,0,.05)'}}>
        <div style={{font:'400 14px/1.4 var(--font-ui)',color:'var(--gray)'}}>Reply to Claude…</div>
        <div style={{display:'flex',gap:10,alignItems:'center',marginTop:8}}>
          <span style={{font:'500 12px/1 var(--font-ui)',color:'var(--gray)'}}>＠ file</span>
          <span style={{font:'500 12px/1 var(--font-ui)',color:'var(--gray)'}}>/ skill</span>
          <span style={{flex:1}}/>
          <span style={{width:30,height:30,borderRadius:15,background:'var(--orange)',display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#fff',font:'500 13px/1 var(--font-ui)'}}>↑</span>
        </div>
      </div>
    </Phone>
  );
}

function C5User({ children }) {
  return (
    <div style={{alignSelf:'flex-end',maxWidth:'90%',padding:'10px 14px',
      background:'var(--ink)',color:'var(--cream)',borderRadius:'16px 16px 4px 16px',
      font:'400 13px/1.45 var(--font-ui)',letterSpacing:'-.005em'}}>{children}</div>
  );
}
function C5Claude({ children }) {
  return (
    <div style={{display:'flex',gap:10,alignItems:'flex-start'}}>
      <Avatar bg="var(--orange)" fg="#fff" size={26}>C</Avatar>
      <div style={{flex:1,minWidth:0,font:'400 13px/1.5 var(--font-ui)',color:'var(--ink)'}}>{children}</div>
    </div>
  );
}
function C5InlineTool({ icon='◇', name, arg, running }) {
  return (
    <div style={{margin:'8px 0',padding:'8px 10px',
      background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:8,
      display:'flex',gap:8,alignItems:'center',
      font:'500 11px/1 var(--font-mono)'}}>
      <span style={{width:20,height:20,borderRadius:5,background:'var(--paper)',display:'inline-flex',alignItems:'center',justifyContent:'center',
        color:running?'var(--orange)':'var(--gold)',fontSize:11}}>{running?'◌':icon}</span>
      <span style={{color:'var(--ink)'}}>{name}</span>
      <span style={{color:'var(--gray)',flex:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>({arg})</span>
      {running ? <span style={{color:'var(--orange)'}}>running…</span> : <span style={{color:'var(--gray)'}}>↗</span>}
    </div>
  );
}
function C5InlineDiff() {
  return (
    <div style={{margin:'8px 0',border:'1px solid var(--gray-3)',borderRadius:8,overflow:'hidden',background:'var(--paper)'}}>
      <div style={{padding:'7px 10px',background:'var(--cream)',font:'500 11px/1 var(--font-mono)',color:'var(--ink)',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <span>router.ts</span>
        <span style={{color:'var(--gray)',display:'flex',gap:6}}><span style={{color:'var(--green)'}}>+18</span><span style={{color:'var(--red)'}}>−7</span></span>
      </div>
      <div style={{padding:'4px 0',font:'400 10.5px/1.55 var(--font-mono)'}}>
        {DIFF_LINES.slice(0,5).map((l,i)=>(
          <div key={i} style={{padding:'0 10px',display:'flex',gap:6,
            background:l.t==='+'?'rgba(92,138,90,.10)':l.t==='-'?'rgba(184,84,71,.10)':'transparent',
            color:l.t==='h'?'var(--gray)':'var(--ink)'}}>
            <span style={{width:8,color:l.t==='+'?'var(--green)':l.t==='-'?'var(--red)':'var(--gray-2)'}}>{l.t==='+'?'+':l.t==='-'?'−':' '}</span>
            <span style={{whiteSpace:'pre',overflow:'hidden',textOverflow:'ellipsis'}}>{l.s}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function D5DeskHome() {
  return (
    <Desk url="eldir.local">
      <div style={{display:'grid',gridTemplateColumns:'260px 1fr',height:'100%'}}>
        {/* sidebar */}
        <div style={{borderRight:'1px solid var(--gray-3)',background:'var(--cream)',display:'flex',flexDirection:'column'}}>
          <div style={{padding:'18px 18px 14px',display:'flex',alignItems:'center',gap:10}}>
            <span style={{width:28,height:28,borderRadius:8,background:'var(--orange)',display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#fff',font:'700 14px/1 var(--font-ui)'}}>E</span>
            <span style={{font:'600 15px/1 var(--font-ui)',letterSpacing:'-.01em'}}>Eldir</span>
            <span style={{flex:1}}/>
            <span style={{font:'500 16px/1 var(--font-ui)',color:'var(--gray)'}}>✎</span>
          </div>
          <div style={{padding:'4px 12px'}}>
            <div style={{padding:'10px 14px',background:'var(--paper)',border:'1px solid var(--gray-3)',borderRadius:8,
              display:'flex',gap:10,alignItems:'center'}}>
              <span style={{color:'var(--orange)'}}>+</span>
              <span style={{font:'500 13px/1 var(--font-ui)',color:'var(--ink)'}}>New conversation</span>
              <span style={{flex:1}}/>
              <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)',padding:'3px 5px',background:'var(--cream-2)',borderRadius:3}}>⌘N</span>
            </div>
          </div>
          <div style={{padding:'18px 20px 6px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Today</div>
          {SESSIONS.map(s=>(
            <div key={s.id} style={{padding:'9px 16px',margin:'1px 8px',borderRadius:6,
              background:s.id==='s1'?'var(--cream-2)':'transparent',
              display:'flex',gap:9,alignItems:'flex-start'}}>
              <div style={{paddingTop:3}}><StateDot s={s.state} size={7}/></div>
              <div style={{flex:1,minWidth:0}}>
                <div style={{font:'500 13px/1.3 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary}</div>
                <div style={{font:'400 10px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>{s.proj} · {s.dur}</div>
              </div>
            </div>
          ))}
          <div style={{padding:'18px 20px 6px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Yesterday</div>
          {[
            ['Add OAuth flow for Forgejo','atelier'],
            ['Fix flaky lumen e2e','lumen'],
            ['Plan v0.4 release notes','kiln'],
          ].map(([t,p],i)=>(
            <div key={i} style={{padding:'9px 16px',margin:'1px 8px',display:'flex',gap:9,alignItems:'flex-start'}}>
              <div style={{paddingTop:3}}><StateDot s="idle" size={7}/></div>
              <div style={{flex:1,minWidth:0}}>
                <div style={{font:'500 13px/1.3 var(--font-ui)',color:'var(--ink-2)',letterSpacing:'-.01em',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{t}</div>
                <div style={{font:'400 10px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>{p}</div>
              </div>
            </div>
          ))}
          <div style={{flex:1}}/>
          <div style={{padding:'14px 16px',borderTop:'1px solid var(--gray-3)',display:'flex',gap:8,alignItems:'center'}}>
            <Avatar size={26}>J</Avatar>
            <div style={{flex:1,minWidth:0}}>
              <div style={{font:'500 12px/1 var(--font-ui)',color:'var(--ink)'}}>jules</div>
              <div style={{font:'400 10px/1 var(--font-mono)',color:'var(--gray)',marginTop:3}}>Pro · $1.61 today</div>
            </div>
            <span style={{font:'500 14px/1 var(--font-ui)',color:'var(--gray)'}}>⚙</span>
          </div>
        </div>
        {/* main blank slate */}
        <div style={{display:'flex',flexDirection:'column',padding:'80px 80px 40px',background:'var(--paper)',overflow:'auto'}}>
          <div style={{maxWidth:680,margin:'0 auto',width:'100%'}}>
            <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:18}}>
              <span style={{width:42,height:42,borderRadius:14,background:'var(--orange)',display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#fff',font:'700 19px/1 var(--font-ui)'}}>C</span>
              <div>
                <div style={{font:'600 22px/1 var(--font-ui)',letterSpacing:'-.02em'}}>What are we building today?</div>
                <div style={{font:'400 13px/1.4 var(--font-ui)',color:'var(--gray)',marginTop:5}}>Pick a project, describe the change, Claude takes it from there.</div>
              </div>
            </div>
            {/* composer */}
            <div style={{padding:'18px 22px 14px',background:'#fff',border:'1px solid var(--gray-3)',borderRadius:18,
              boxShadow:'0 4px 18px rgba(0,0,0,.05)'}}>
              <div style={{font:'400 16px/1.5 var(--font-ui)',color:'var(--gray)'}}>Tell Claude what to do…</div>
              <div style={{display:'flex',gap:8,alignItems:'center',marginTop:14}}>
                <Chip label="eldir" git="fj" active/>
                <Chip label="Pick skill"/>
                <Chip label="@ file"/>
                <span style={{flex:1}}/>
                <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>⌘↵</span>
                <span style={{width:36,height:36,borderRadius:18,background:'var(--orange)',display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#fff',font:'500 16px/1 var(--font-ui)'}}>↑</span>
              </div>
            </div>
            {/* prompt suggestions */}
            <div style={{marginTop:20,display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
              {[
                ['◇','Refactor the SSE router for clean reconnects','eldir'],
                ['◇','Generate tests for auth/token rotation','atelier'],
                ['◐','Audit dependencies and bump majors','lumen'],
                ['+','Open a fresh conversation in any project','-'],
              ].map((s,i)=>(
                <div key={i} style={{padding:'14px 16px',background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:12}}>
                  <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                    <span style={{width:22,height:22,borderRadius:6,background:'var(--paper)',color:'var(--orange)',display:'inline-flex',alignItems:'center',justifyContent:'center',font:'500 13px/1 var(--font-mono)'}}>{s[0]}</span>
                    <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>{s[2]}</span>
                  </div>
                  <div style={{font:'500 14px/1.4 var(--font-ui)',letterSpacing:'-.01em',color:'var(--ink)'}}>{s[1]}</div>
                </div>
              ))}
            </div>
            <div style={{marginTop:30,fontSize:11,color:'var(--gray)',textAlign:'center'}}>Claude has access to {PROJECTS.length} projects · 3 skills · ollama (off)</div>
          </div>
        </div>
      </div>
    </Desk>
  );
}

function Chip({ label, git, active }) {
  return (
    <span style={{padding:'5px 10px',borderRadius:14,
      background:active?'var(--cream-2)':'var(--cream)',
      border:'1px solid var(--gray-3)',
      font:'500 11px/1 var(--font-ui)',color:active?'var(--ink)':'var(--gray)',
      display:'inline-flex',gap:5,alignItems:'center'}}>
      {git && <GitMark kind={git} size={10} color={active?'var(--orange)':'var(--gray)'}/>}
      {label}
    </span>
  );
}

function D5DeskSession() {
  return (
    <Desk url="eldir.local/c/router-fix">
      <div style={{display:'grid',gridTemplateColumns:'260px 1fr 320px',height:'100%'}}>
        <div style={{borderRight:'1px solid var(--gray-3)',background:'var(--cream)',padding:'14px 0'}}>
          <div style={{padding:'4px 18px 12px',display:'flex',alignItems:'center',gap:10}}>
            <span style={{width:26,height:26,borderRadius:7,background:'var(--orange)',display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#fff',font:'700 13px/1 var(--font-ui)'}}>E</span>
            <span style={{font:'600 14px/1 var(--font-ui)'}}>Eldir</span>
          </div>
          <div style={{padding:'8px 12px'}}>
            <div style={{padding:'9px 12px',background:'var(--paper)',border:'1px solid var(--gray-3)',borderRadius:8,
              display:'flex',gap:9,alignItems:'center',font:'500 12px/1 var(--font-ui)'}}>
              <span style={{color:'var(--orange)'}}>+</span> New conversation
            </div>
          </div>
          <div style={{padding:'18px 20px 6px',font:'500 10px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase'}}>Today</div>
          {SESSIONS.map(s=>(
            <div key={s.id} style={{padding:'9px 16px',margin:'1px 8px',borderRadius:6,
              background:s.id==='s1'?'var(--cream-2)':'transparent',
              display:'flex',gap:9,alignItems:'flex-start'}}>
              <div style={{paddingTop:3}}><StateDot s={s.state} size={7}/></div>
              <div style={{flex:1,minWidth:0}}>
                <div style={{font:'500 13px/1.3 var(--font-ui)',color:'var(--ink)',letterSpacing:'-.01em',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary}</div>
                <div style={{font:'400 10px/1 var(--font-mono)',color:'var(--gray)',marginTop:4}}>{s.proj} · {s.dur}</div>
              </div>
            </div>
          ))}
        </div>
        {/* main convo */}
        <div style={{display:'flex',flexDirection:'column',background:'var(--paper)'}}>
          <div style={{padding:'14px 32px',borderBottom:'1px solid var(--gray-3)',display:'flex',alignItems:'center',gap:14}}>
            <div style={{flex:1}}>
              <div style={{font:'600 16px/1.2 var(--font-ui)',letterSpacing:'-.02em'}}>Refactor session router for SSE reconnect</div>
              <div style={{font:'400 11px/1 var(--font-mono)',color:'var(--gray)',marginTop:5,display:'inline-flex',gap:6,alignItems:'center'}}>
                <GitMark kind="fj" size={11} color="var(--gray)"/>eldir · feat/sessions · sonnet 4.5
              </div>
            </div>
            <StatePill s="thinking"/>
            <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>14:22 · 64k · $0.21</span>
          </div>
          <div style={{flex:1,padding:'28px 32px 16px',overflow:'auto',display:'flex',flexDirection:'column',gap:18}}>
            <C5User>The session router drops SSE messages when the client reconnects mid-stream. Investigate.</C5User>
            <C5Claude>
              <div>Reading the router to see how it buffers messages between connections.</div>
              <C5InlineTool icon="📄" name="read_file" arg="src/server/sessions/router.ts"/>
              <div style={{marginTop:10}}>The buffer is keyed on socket id, not session id - that's why a reconnect loses everything. Switching to a per-session ring buffer keyed on session id, with replay-from-last-ack on reconnect.</div>
              <C5InlineDiff/>
              <C5InlineTool icon="▶" name="run_bash" arg="pnpm test --filter=core" running/>
              <div style={{marginTop:10,color:'var(--gray)',fontSize:12}}>Tests are running - I'll report back when the run finishes.</div>
            </C5Claude>
          </div>
          <div style={{padding:'12px 32px 22px',borderTop:'1px solid var(--gray-3)'}}>
            <div style={{padding:'14px 18px',background:'#fff',border:'1px solid var(--gray-3)',borderRadius:16,
              boxShadow:'0 4px 14px rgba(0,0,0,.05)'}}>
              <div style={{font:'400 14px/1.5 var(--font-ui)',color:'var(--gray)'}}>Reply to Claude…</div>
              <div style={{display:'flex',gap:8,alignItems:'center',marginTop:10}}>
                <Chip label="@ file"/>
                <Chip label="/ skill"/>
                <span style={{flex:1}}/>
                <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>⌘↵</span>
                <span style={{width:32,height:32,borderRadius:16,background:'var(--orange)',display:'inline-flex',alignItems:'center',justifyContent:'center',color:'#fff',font:'500 14px/1 var(--font-ui)'}}>↑</span>
              </div>
            </div>
          </div>
        </div>
        {/* right: live artifacts */}
        <div style={{borderLeft:'1px solid var(--gray-3)',background:'var(--paper)',padding:'18px 18px',overflow:'auto'}}>
          <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase',marginBottom:10}}>Files in flight</div>
          {['router.ts','router.test.ts','types.ts'].map((f,i)=>(
            <div key={f} style={{padding:'9px 12px',margin:'2px 0',background:i===0?'var(--cream-2)':'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:8,
              display:'flex',gap:8,alignItems:'center'}}>
              <span style={{width:22,height:22,borderRadius:5,background:'var(--paper)',display:'inline-flex',alignItems:'center',justifyContent:'center',font:'500 11px/1 var(--font-mono)',color:'var(--orange)'}}>◇</span>
              <span style={{flex:1,font:'500 12px/1.2 var(--font-mono)',color:'var(--ink)'}}>{f}</span>
              {i===0 && <span style={{font:'500 10px/1 var(--font-mono)',color:'var(--gray)'}}>+18 −7</span>}
            </div>
          ))}
          <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase',margin:'18px 0 10px'}}>Run output</div>
          <div style={{padding:'12px 14px',background:'var(--ink)',color:'var(--cream)',borderRadius:8,
            font:'400 11px/1.5 var(--font-mono)'}}>
            <div style={{color:'var(--gray-2)'}}>$ pnpm test --filter=core</div>
            <div>core test/router.test.ts</div>
            <div style={{color:'var(--gold)'}}>  ✓ buffers by session id (12ms)</div>
            <div style={{color:'var(--gold)'}}>  ✓ replays on reconnect (8ms)</div>
            <div style={{color:'var(--orange)'}}>  ◌ subscribes survive close…</div>
          </div>
          <div style={{font:'500 11px/1 var(--font-ui)',color:'var(--gray)',letterSpacing:'.08em',textTransform:'uppercase',margin:'18px 0 10px'}}>Spend</div>
          <div style={{padding:14,background:'var(--cream)',border:'1px solid var(--gray-3)',borderRadius:8}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline'}}>
              <span style={{font:'600 22px/1 var(--font-ui)',letterSpacing:'-.02em'}}>$0.21</span>
              <span style={{font:'500 11px/1 var(--font-mono)',color:'var(--gray)'}}>cap $2.00</span>
            </div>
            <div style={{marginTop:10}}><Spark w={250} h={32} fill="rgba(217,119,87,.12)"/></div>
          </div>
        </div>
      </div>
    </Desk>
  );
}

Object.assign(window, { D5MobileHome, D5MobileSession, D5DeskHome, D5DeskSession });
