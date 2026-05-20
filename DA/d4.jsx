// Direction 4 - "Terminal-first"
// tmux / Warp / Claude Code itself. Dense, monospace, keyboard-shortcut visible.

const TERM_BG  = '#171411';
const TERM_FG  = '#E8E2D5';
const TERM_DIM = '#807A6F';
const TERM_HI  = '#D97757';
const TERM_GD  = '#C9A87C';
const TERM_GR  = '#5C8A5A';
const TERM_RD  = '#B85447';
const TERM_BL  = '#5A7A9A';
const TERM_AC  = '#262220';

function TermShell({ children, title='eldir', tabs=[] }) {
  return (
    <div style={{height:'100%',background:TERM_BG,color:TERM_FG,
      font:'400 12px/1.55 var(--font-mono)',display:'flex',flexDirection:'column'}}>
      {/* tmux-ish status bar at top */}
      <div style={{display:'flex',background:'#0E0C0A',padding:'0 0 0 8px',borderBottom:`1px solid ${TERM_AC}`}}>
        <span style={{padding:'4px 10px',background:TERM_HI,color:'#1A1310',font:'600 11px/1.6 var(--font-mono)',letterSpacing:'.06em'}}>ELDIR</span>
        {tabs.map((t,i)=>(
          <span key={i} style={{padding:'4px 10px',
            background:t.active?TERM_AC:'transparent',
            color:t.active?TERM_FG:TERM_DIM,
            font:'500 11px/1.6 var(--font-mono)',
            borderRight:`1px solid ${TERM_AC}`,
            display:'inline-flex',alignItems:'center',gap:6}}>
            <span style={{color:t.active?TERM_HI:TERM_DIM}}>{i}:</span>{t.label}
            {t.state && <StateDot s={t.state} size={6}/>}
          </span>
        ))}
        <span style={{flex:1}}/>
        <span style={{padding:'4px 10px',color:TERM_DIM,font:'500 11px/1.6 var(--font-mono)'}}>419k · $1.61 · 09:41</span>
      </div>
      <div style={{flex:1,minHeight:0,position:'relative'}}>{children}</div>
    </div>
  );
}

function TermLine({ children, color }) {
  return <div style={{padding:'0 12px',color:color||TERM_FG,whiteSpace:'pre',overflow:'hidden',textOverflow:'ellipsis'}}>{children}</div>;
}

function D4MobileHome() {
  return (
    <Phone>
      <div style={{height:'calc(100% - 30px)',background:TERM_BG}}>
        <TermShell tabs={[
          {label:'home', active:true},
          {label:'eldir/s1', state:'thinking'},
          {label:'lumen/s3', state:'input'},
        ]}>
          <div style={{padding:'12px 0'}}>
            <TermLine color={TERM_DIM}>{'$ eldir status'}</TermLine>
            <TermLine color={TERM_DIM}>{'─'.repeat(48)}</TermLine>
            <TermLine><span style={{color:TERM_HI}}>SESSIONS</span><span style={{color:TERM_DIM}}>{'  '}4 active · 1 awaiting</span></TermLine>
            <TermLine><span style={{color:TERM_GD}}>TOKENS  </span><span style={{color:TERM_FG}}>419k</span><span style={{color:TERM_DIM}}>{' / '}$1.61 today</span></TermLine>
            <TermLine color={TERM_DIM}>{'─'.repeat(48)}</TermLine>
            <div style={{height:8}}/>
            <TermLine color={TERM_DIM}># sessions</TermLine>
            {SESSIONS.map((s,i)=>(
              <div key={s.id} style={{padding:'2px 12px',display:'flex',gap:8,
                background:i===0?TERM_AC:'transparent'}}>
                <span style={{color:TERM_HI,width:18}}>{i+1}</span>
                <StateDot s={s.state} size={6}/>
                <span style={{color:TERM_FG,width:62}}>{s.proj}/{s.id}</span>
                <span style={{color:TERM_DIM,flex:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary.slice(0,28)}</span>
              </div>
            ))}
            <div style={{height:8}}/>
            <TermLine color={TERM_DIM}># projects (5)</TermLine>
            {PROJECTS.map((p,i)=>(
              <div key={p.id} style={{padding:'1px 12px',display:'flex',gap:6,color:TERM_FG}}>
                <span style={{color:TERM_DIM,width:18}}>{['p','q','r','s','t'][i]}</span>
                <span style={{color:p.pv==='gh'?TERM_BL:TERM_HI,width:14}}>{p.pv==='gh'?'Γ':'F'}</span>
                <span style={{width:104}}>{p.name}</span>
                <span style={{color:TERM_DIM,flex:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{p.branch}</span>
                <span style={{color:p.sessions>0?TERM_HI:TERM_DIM,width:18,textAlign:'right'}}>{p.sessions||'·'}</span>
              </div>
            ))}
            <div style={{height:10}}/>
            <TermLine><span style={{color:TERM_HI}}>{'> '}</span><span style={{color:TERM_FG,background:TERM_FG,opacity:.6,width:9,height:14,display:'inline-block',verticalAlign:'middle'}}/></TermLine>
          </div>
        </TermShell>
        {/* bottom kb-shortcut bar */}
        <div style={{position:'absolute',bottom:0,left:0,right:0,height:32,background:'#0E0C0A',
          borderTop:`1px solid ${TERM_AC}`,display:'flex',alignItems:'center',padding:'0 8px',
          font:'500 10px/1 var(--font-mono)',color:TERM_DIM,gap:12,overflow:'hidden'}}>
          <Kbd k="^N" l="new"/><Kbd k="^J" l="jump"/><Kbd k="1-9" l="tab"/><Kbd k="↵" l="open"/>
        </div>
      </div>
    </Phone>
  );
}

function Kbd({ k, l }) {
  return (
    <span style={{display:'inline-flex',gap:4,alignItems:'center'}}>
      <span style={{padding:'2px 5px',background:TERM_AC,color:TERM_HI,borderRadius:2,
        font:'600 9px/1 var(--font-mono)'}}>{k}</span>
      <span style={{color:TERM_DIM}}>{l}</span>
    </span>
  );
}

function D4MobileSession() {
  return (
    <Phone>
      <div style={{height:'calc(100% - 30px)',background:TERM_BG}}>
        <TermShell tabs={[
          {label:'home'},
          {label:'eldir/s1', state:'thinking', active:true},
          {label:'lumen/s3', state:'input'},
        ]}>
          <div style={{padding:'10px 0',height:'100%',display:'flex',flexDirection:'column'}}>
            {/* header line */}
            <TermLine color={TERM_DIM}>{'─── eldir/s1 · feat/sessions · 14:22 · 64k · $0.21 ───'.slice(0,46)}</TermLine>
            <div style={{flex:1,paddingTop:6,overflow:'hidden'}}>
              <TermLine color={TERM_BL}>you {'>'}</TermLine>
              <TermLine>{'  the session router drops SSE'}</TermLine>
              <TermLine>{'  messages on reconnect.'}</TermLine>
              <div style={{height:6}}/>
              <TermLine color={TERM_HI}>claude {'>'}</TermLine>
              <TermLine>{'  buffer is keyed on socket id,'}</TermLine>
              <TermLine>{'  not session id. switching to'}</TermLine>
              <TermLine>{'  a per-session ring buffer.'}</TermLine>
              <div style={{height:6}}/>
              <TermLine color={TERM_GD}>{'⟶ tool: edit_file router.ts'}</TermLine>
              <TermLine color={TERM_DIM}>{'  +18 −7'}</TermLine>
              <div style={{height:4}}/>
              <TermLine><span style={{color:TERM_RD}}>-</span> <span style={{color:TERM_DIM}}>const buffers = Map&lt;Soc…</span></TermLine>
              <TermLine><span style={{color:TERM_GR}}>+</span> <span style={{color:TERM_FG}}>const buffers = Map&lt;Ses…</span></TermLine>
              <div style={{height:6}}/>
              <TermLine color={TERM_GD}>{'⟶ tool: run_bash pnpm test'}</TermLine>
              <TermLine color={TERM_HI}>{'  ◌ running…'}</TermLine>
            </div>
            {/* prompt */}
            <div style={{padding:'8px 10px 4px',borderTop:`1px solid ${TERM_AC}`}}>
              <div style={{font:'500 11px/1.4 var(--font-mono)'}}>
                <span style={{color:TERM_HI}}>$ </span>
                <span style={{color:TERM_FG,background:TERM_AC,padding:'1px 0'}}>reply or /command</span>
                <span style={{display:'inline-block',width:8,height:13,background:TERM_FG,verticalAlign:'-2px',marginLeft:2,opacity:.7}}/>
              </div>
            </div>
          </div>
        </TermShell>
        <div style={{position:'absolute',bottom:0,left:0,right:0,height:32,background:'#0E0C0A',
          borderTop:`1px solid ${TERM_AC}`,display:'flex',alignItems:'center',padding:'0 8px',
          font:'500 10px/1 var(--font-mono)',color:TERM_DIM,gap:10,overflow:'hidden'}}>
          <Kbd k="^D" l="diff"/><Kbd k="^R" l="run"/><Kbd k="^P" l="pause"/><Kbd k="^[" l="back"/>
        </div>
      </div>
    </Phone>
  );
}

function D4DeskHome() {
  return (
    <Desk url="eldir.local">
      <TermShell tabs={[
        {label:'home', active:true},
        {label:'eldir/s1', state:'thinking'},
        {label:'eldir/s2', state:'tool'},
        {label:'lumen/s3', state:'input'},
        {label:'atelier/s4', state:'idle'},
      ]}>
        {/* split panes */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gridTemplateRows:'1fr 1fr',height:'100%'}}>
          {/* sessions pane */}
          <div style={{borderRight:`1px solid ${TERM_AC}`,padding:'8px 0',gridRow:'span 2'}}>
            <div style={{padding:'2px 12px',color:TERM_HI,font:'600 11px/1.6 var(--font-mono)',letterSpacing:'.05em'}}>── SESSIONS ─────────────────</div>
            {SESSIONS.map((s,i)=>(
              <div key={s.id} style={{padding:'4px 12px',background:i===0?TERM_AC:'transparent'}}>
                <div style={{display:'flex',gap:8,alignItems:'center'}}>
                  <span style={{color:TERM_DIM,width:12}}>{i+1}</span>
                  <StateDot s={s.state} size={7}/>
                  <span style={{color:TERM_FG,fontWeight:600}}>{s.proj}/{s.id}</span>
                  <span style={{flex:1}}/>
                  <span style={{color:TERM_DIM,fontSize:11}}>{s.dur}</span>
                </div>
                <div style={{paddingLeft:28,color:TERM_DIM,fontSize:11,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{s.summary}</div>
                <div style={{paddingLeft:28,color:TERM_GD,fontSize:11,marginTop:2}}>◊ {s.tokens} · {s.cost}</div>
              </div>
            ))}
            <div style={{padding:'10px 12px 4px',color:TERM_HI,font:'600 11px/1.6 var(--font-mono)'}}>── PROJECTS ─────────────────</div>
            {PROJECTS.map((p,i)=>(
              <div key={p.id} style={{padding:'2px 12px',display:'flex',gap:6}}>
                <span style={{color:TERM_DIM,width:14}}>{i+1}</span>
                <span style={{color:p.pv==='gh'?TERM_BL:TERM_HI,width:14}}>{p.pv==='gh'?'Γ':'F'}</span>
                <span style={{color:TERM_FG,width:108}}>{p.name}</span>
                <span style={{color:TERM_DIM,flex:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{p.branch}</span>
                <span style={{color:p.sessions>0?TERM_HI:TERM_DIM,width:24,textAlign:'right'}}>{p.sessions>0?`${p.sessions} live`:'·'}</span>
              </div>
            ))}
          </div>
          {/* live log pane */}
          <div style={{borderRight:`1px solid ${TERM_AC}`,borderBottom:`1px solid ${TERM_AC}`,padding:'8px 0'}}>
            <div style={{padding:'2px 12px',color:TERM_HI,font:'600 11px/1.6 var(--font-mono)'}}>── STREAM ──────────────</div>
            {[
              ['09:41:07', 's1', 'thinking', 'switching to per-session ring buffer'],
              ['09:41:02', 's1', 'tool',     'edit_file router.ts +18 −7'],
              ['09:40:58', 's2', 'tool',     'run_bash pnpm test --filter=core'],
              ['09:40:45', 's3', 'input',    'awaiting safelist confirmation'],
              ['09:40:14', 's1', 'tool',     'read_file router.ts'],
              ['09:39:50', 's1', 'thinking', 'investigating buffer keys'],
              ['09:39:11', 's4', 'idle',     'session ended (rotation done)'],
            ].map((e,i)=>(
              <div key={i} style={{padding:'1px 12px',display:'flex',gap:8,fontSize:11}}>
                <span style={{color:TERM_DIM,width:54}}>{e[0]}</span>
                <span style={{color:TERM_HI,width:24}}>{e[1]}</span>
                <span style={{color:STATES[e[2]].color,width:60}}>{STATES[e[2]].label}</span>
                <span style={{color:TERM_FG,flex:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{e[3]}</span>
              </div>
            ))}
          </div>
          {/* stats pane */}
          <div style={{borderBottom:`1px solid ${TERM_AC}`,padding:'8px 0'}}>
            <div style={{padding:'2px 12px',color:TERM_HI,font:'600 11px/1.6 var(--font-mono)'}}>── SPEND ───────────────</div>
            <div style={{padding:'10px 12px',color:TERM_FG,fontFamily:'var(--font-mono)'}}>
              <div style={{fontSize:32,fontWeight:600,letterSpacing:'-.02em'}}>$1.61<span style={{color:TERM_DIM,fontSize:14,fontWeight:400}}> / $8.00</span></div>
              <div style={{color:TERM_DIM,fontSize:11,marginTop:4}}>today · 419k tokens</div>
              <div style={{marginTop:14}}>
                <Spark data={[2,4,3,7,5,8,11,9,12]} w={290} h={48} color={TERM_HI} fill="rgba(217,119,87,.18)"/>
              </div>
            </div>
            <div style={{padding:'4px 12px',color:TERM_DIM,fontSize:11,display:'flex',justifyContent:'space-between'}}>
              <span>per project</span><span>tokens · cost</span>
            </div>
            {[['eldir','220k','$0.74'],['lumen','67k','$0.21'],['atelier','132k','$0.66']].map((r,i)=>(
              <div key={i} style={{padding:'1px 12px',display:'flex',gap:8,fontSize:11}}>
                <span style={{color:TERM_FG,width:80}}>{r[0]}</span>
                <span style={{color:TERM_GD,width:60}}>{r[1]}</span>
                <span style={{color:TERM_FG}}>{r[2]}</span>
              </div>
            ))}
          </div>
          {/* prompt pane (full width bottom) */}
          <div style={{gridColumn:'2 / span 2',padding:'8px 0',display:'flex',flexDirection:'column'}}>
            <div style={{padding:'2px 12px',color:TERM_HI,font:'600 11px/1.6 var(--font-mono)'}}>── PROMPT ──────────────────────────────────</div>
            <div style={{flex:1,padding:'10px 14px',color:TERM_FG,fontSize:13}}>
              <div style={{color:TERM_DIM,marginBottom:6}}>{'$ eldir new --project=eldir --skill=router-fixer'}</div>
              <div style={{color:TERM_DIM,marginBottom:8}}>{'? Which mission template?'}</div>
              <div style={{color:TERM_HI}}>{'  → router-fixer  '}<span style={{color:TERM_DIM}}>{' (system prompt + skills)'}</span></div>
              <div style={{color:TERM_DIM}}>{'    code-review'}</div>
              <div style={{color:TERM_DIM}}>{'    test-generator'}</div>
              <div style={{color:TERM_DIM}}>{'    custom…'}</div>
              <div style={{height:14}}/>
              <div>
                <span style={{color:TERM_HI}}>{'$ '}</span>
                <span style={{color:TERM_FG}}>fix sse reconnect bug in router</span>
                <span style={{display:'inline-block',width:8,height:14,background:TERM_FG,verticalAlign:'-2px',marginLeft:1,opacity:.85}}/>
              </div>
            </div>
            <div style={{padding:'6px 12px',background:'#0E0C0A',borderTop:`1px solid ${TERM_AC}`,
              display:'flex',gap:14,fontSize:11,color:TERM_DIM}}>
              <Kbd k="^N" l="new session"/><Kbd k="^K" l="jump"/><Kbd k="1–9" l="switch tab"/>
              <Kbd k="^/" l="search"/><Kbd k="?" l="help"/>
              <span style={{flex:1}}/>
              <span>auth: pro · model: sonnet 4.5 · ollama:off</span>
            </div>
          </div>
        </div>
      </TermShell>
    </Desk>
  );
}

function D4DeskSession() {
  return (
    <Desk url="eldir.local/s1">
      <TermShell tabs={[
        {label:'home'},
        {label:'eldir/s1', state:'thinking', active:true},
        {label:'eldir/s2', state:'tool'},
        {label:'lumen/s3', state:'input'},
      ]}>
        <div style={{display:'grid',gridTemplateColumns:'1.4fr 1fr',height:'100%'}}>
          {/* left pane: chat stream */}
          <div style={{borderRight:`1px solid ${TERM_AC}`,display:'flex',flexDirection:'column'}}>
            <div style={{padding:'4px 12px',color:TERM_DIM,font:'500 11px/1.6 var(--font-mono)',borderBottom:`1px solid ${TERM_AC}`}}>
              ── eldir/s1 · feat/sessions · 14:22 · 64k · $0.21 ── <span style={{color:TERM_HI}}>thinking</span>
            </div>
            <div style={{flex:1,padding:'12px 14px',overflow:'auto',fontSize:12.5,color:TERM_FG}}>
              <div style={{color:TERM_BL}}>you {'>'}</div>
              <div style={{paddingLeft:16,marginBottom:14}}>The session router drops SSE messages when the client reconnects mid-stream. Investigate.</div>
              <div style={{color:TERM_HI}}>claude {'>'}</div>
              <div style={{paddingLeft:16,marginBottom:14}}>Reading the router to see how it buffers messages between connections.</div>
              <div style={{color:TERM_GD,fontSize:12}}>⟶ tool · read_file <span style={{color:TERM_DIM}}>src/server/sessions/router.ts</span> <span style={{color:TERM_DIM}}>(142 lines)</span></div>
              <div style={{height:10}}/>
              <div style={{color:TERM_HI}}>claude {'>'}</div>
              <div style={{paddingLeft:16,marginBottom:14}}>The buffer is keyed on socket id, not session id - that's why a reconnect loses everything. Switching to a per-session ring buffer.</div>
              <div style={{color:TERM_GD,fontSize:12}}>⟶ tool · edit_file <span style={{color:TERM_DIM}}>router.ts</span> <span style={{color:TERM_GR}}>+18</span> <span style={{color:TERM_RD}}>−7</span></div>
              <div style={{height:6}}/>
              <div style={{color:TERM_GD,fontSize:12}}>⟶ tool · run_bash <span style={{color:TERM_DIM}}>pnpm test --filter=core</span> <span style={{color:TERM_HI}}>◌ running</span></div>
              <div style={{height:14}}/>
              <div>
                <span style={{color:TERM_HI}}>{'$ '}</span>
                <span style={{display:'inline-block',width:9,height:15,background:TERM_FG,verticalAlign:'-2px',opacity:.85}}/>
              </div>
            </div>
            <div style={{padding:'6px 12px',background:'#0E0C0A',borderTop:`1px solid ${TERM_AC}`,display:'flex',gap:14,fontSize:11,color:TERM_DIM}}>
              <Kbd k="↵" l="send"/><Kbd k="^D" l="diff"/><Kbd k="^R" l="rerun"/><Kbd k="^P" l="pause"/>
              <span style={{flex:1}}/><span style={{color:TERM_DIM}}>14,210 ctx · 256k cap</span>
            </div>
          </div>
          {/* right: diff + run output */}
          <div style={{display:'grid',gridTemplateRows:'1fr 1fr'}}>
            <div style={{borderBottom:`1px solid ${TERM_AC}`,display:'flex',flexDirection:'column'}}>
              <div style={{padding:'4px 12px',color:TERM_DIM,font:'500 11px/1.6 var(--font-mono)'}}>── DIFF · router.ts ─── <span style={{color:TERM_GR}}>+18</span> <span style={{color:TERM_RD}}>−7</span></div>
              <div style={{flex:1,fontSize:12,padding:'4px 0',overflow:'auto'}}>
                {DIFF_LINES.map((l,i)=>(
                  <div key={i} style={{padding:'0 12px',display:'flex',gap:8,
                    background:l.t==='+'?'rgba(92,138,90,.16)':l.t==='-'?'rgba(184,84,71,.16)':'transparent',
                    color:l.t==='h'?TERM_DIM:TERM_FG}}>
                    <span style={{color:TERM_DIM,width:24,textAlign:'right'}}>{i+34}</span>
                    <span style={{width:10,color:l.t==='+'?TERM_GR:l.t==='-'?TERM_RD:TERM_DIM}}>{l.t==='+'?'+':l.t==='-'?'−':' '}</span>
                    <span style={{whiteSpace:'pre'}}>{l.s}</span>
                  </div>
                ))}
              </div>
            </div>
            <div style={{display:'flex',flexDirection:'column'}}>
              <div style={{padding:'4px 12px',color:TERM_DIM,font:'500 11px/1.6 var(--font-mono)'}}>── RUN · pnpm test --filter=core ──</div>
              <div style={{flex:1,fontSize:12,padding:'4px 12px',overflow:'auto'}}>
                <div style={{color:TERM_DIM}}>$ pnpm test --filter=core</div>
                <div style={{color:TERM_FG}}>core test/router.test.ts</div>
                <div style={{color:TERM_GR}}>  ✓ buffers messages by session id (12ms)</div>
                <div style={{color:TERM_GR}}>  ✓ replays missed on reconnect (8ms)</div>
                <div style={{color:TERM_GR}}>  ✓ drops oldest at ring cap (3ms)</div>
                <div style={{color:TERM_HI}}>  ◌ subscribes survive close/open  ··· running</div>
                <div style={{height:8}}/>
                <div style={{color:TERM_DIM}}>3 passed · 1 running · 0 failed</div>
              </div>
            </div>
          </div>
        </div>
      </TermShell>
    </Desk>
  );
}

Object.assign(window, { D4MobileHome, D4MobileSession, D4DeskHome, D4DeskSession });
