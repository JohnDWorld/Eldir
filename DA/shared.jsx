// Shared atoms across all 5 directions

const STATES = {
  idle:     { label:'idle',     cls:'idle',     color:'#B8B3AB' },
  thinking: { label:'thinking', cls:'thinking', color:'#D97757' },
  tool:     { label:'tool use', cls:'tool',     color:'#C9A87C' },
  input:    { label:'awaiting', cls:'input',    color:'#D9A24A' },
  blocked:  { label:'blocked',  cls:'blocked',  color:'#B85447' },
};

function StateDot({ s='idle', size=8 }) {
  return <span className={`dot ${STATES[s].cls}`} style={{width:size,height:size}} />;
}
function StatePill({ s='idle', textColor }) {
  return (
    <span className="statepill" style={textColor?{color:textColor}:undefined}>
      <StateDot s={s}/> {STATES[s].label}
    </span>
  );
}

function GitMark({ kind='gh', size=12, color='currentColor' }) {
  if (kind === 'fj') return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M8 1.5c1.6 2.6-1 3.6 1 6.4 1 1.4 2.7 1 2.7 2.8a3.7 3.7 0 1 1-7.4 0c0-1.7 1.7-1.7 1.7-3.5S6.6 4 8 1.5z"
        stroke={color} strokeWidth="1.1" strokeLinejoin="round"/>
    </svg>
  );
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill={color}>
      <path d="M8 .5a7.5 7.5 0 0 0-2.4 14.6c.4.1.5-.2.5-.4v-1.4c-2 .4-2.5-.9-2.5-.9-.3-.8-.8-1-.8-1-.7-.5.1-.5.1-.5.7.1 1.1.7 1.1.7.7 1.1 1.7.8 2.2.6.1-.5.3-.8.5-1-1.7-.2-3.4-.8-3.4-3.7 0-.8.3-1.5.7-2-.1-.2-.3-.9.1-1.9 0 0 .6-.2 2 .8a7 7 0 0 1 3.6 0c1.4-1 2-.8 2-.8.4 1 .2 1.7.1 1.9.5.5.8 1.2.8 2 0 2.9-1.7 3.5-3.4 3.7.3.2.5.7.5 1.4v2c0 .2.1.5.6.4A7.5 7.5 0 0 0 8 .5z"/>
    </svg>
  );
}

function ProviderBadge({ kind='gh' }) {
  return (
    <span style={{display:'inline-flex',alignItems:'center',gap:4,
      font:'500 9px/1 var(--font-mono)',color:'var(--gray)',
      padding:'3px 5px',borderRadius:3,background:'rgba(139,134,128,.1)',
      textTransform:'lowercase',letterSpacing:'.04em'}}>
      <GitMark kind={kind} size={9}/>{kind==='gh'?'github':'forgejo'}
    </span>
  );
}

function Phone({ children }) {
  return (
    <div className="phone eldir">
      <div className="notch"/>
      <div className="phone-inner">
        <div className="statusbar">
          <span>9:41</span>
          <span style={{display:'flex',gap:5,alignItems:'center'}}>
            <svg width="14" height="9" viewBox="0 0 14 9" fill="#1a1a1a"><rect x="0" y="6" width="2" height="3" rx=".4"/><rect x="3" y="4" width="2" height="5" rx=".4"/><rect x="6" y="2" width="2" height="7" rx=".4"/><rect x="9" y="0" width="2" height="9" rx=".4"/></svg>
            <svg width="20" height="9" viewBox="0 0 20 9"><rect x=".5" y=".5" width="16" height="8" rx="1.5" fill="none" stroke="#1a1a1a"/><rect x="2" y="2" width="13" height="5" rx=".4" fill="#1a1a1a"/><rect x="17" y="3" width="1.5" height="3" rx=".4" fill="#1a1a1a"/></svg>
          </span>
        </div>
        {children}
      </div>
    </div>
  );
}

function Desk({ url='eldir.local', children }) {
  return (
    <div className="desk eldir">
      <div className="deskbar">
        <div className="tl"><span className="r"/><span className="y"/><span className="g"/></div>
        <div className="url">{url}</div>
        <div style={{width:52}}/>
      </div>
      <div style={{position:'absolute',top:36,left:0,right:0,bottom:0,overflow:'hidden'}}>{children}</div>
    </div>
  );
}

function Avatar({ children='J', bg='var(--ink)', fg='var(--cream)', size=22 }) {
  return <span style={{display:'inline-flex',alignItems:'center',justifyContent:'center',
    width:size,height:size,borderRadius:'50%',background:bg,color:fg,
    font:'600 10px/1 var(--font-ui)',flexShrink:0}}>{children}</span>;
}

function Spark({ data=[3,5,4,7,6,8,5,9,7,11,9,12,10,13], w=60, h=18, color='var(--orange)', fill }) {
  const max=Math.max(...data),min=Math.min(...data),span=max-min||1;
  const pts=data.map((v,i)=>`${(i/(data.length-1))*w},${h-((v-min)/span)*(h-2)-1}`).join(' ');
  const area=`0,${h} ${pts} ${w},${h}`;
  return (
    <svg width={w} height={h}>
      {fill && <polygon points={area} fill={fill}/>}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ── Sample data ─────────────────────────────────────────────
const PROJECTS = [
  { id:'eldir',    name:'eldir',         org:'jules',  pv:'fj', branch:'feat/sessions',   sessions:2, last:'2m ago',  tokens:'128k', cost:'$0.42', dirty:7 },
  { id:'lumen',    name:'lumen-web',     org:'jules',  pv:'gh', branch:'main',            sessions:1, last:'14m ago', tokens:'67k',  cost:'$0.21', dirty:0 },
  { id:'atelier',  name:'atelier-api',   org:'jules',  pv:'fj', branch:'fix/auth-token',  sessions:1, last:'1h ago',  tokens:'212k', cost:'$0.74', dirty:3 },
  { id:'kiln',     name:'kiln-cli',      org:'jules',  pv:'gh', branch:'release/0.4',     sessions:0, last:'3h ago',  tokens:'0',    cost:'—',     dirty:0 },
  { id:'mire',     name:'mire-notebook', org:'jules',  pv:'gh', branch:'main',            sessions:0, last:'2d ago',  tokens:'0',    cost:'—',     dirty:0 },
];

const SESSIONS = [
  { id:'s1', proj:'eldir',   state:'thinking', summary:'Refactor session router for SSE reconnect',  tokens:'64k',  cost:'$0.21', dur:'14:22' },
  { id:'s2', proj:'eldir',   state:'tool',     summary:'Run pnpm test --filter=core',                tokens:'12k',  cost:'$0.04', dur:'02:11' },
  { id:'s3', proj:'lumen',   state:'input',    summary:'Tailwind purge — confirm safelist?',         tokens:'67k',  cost:'$0.21', dur:'08:45' },
  { id:'s4', proj:'atelier', state:'idle',     summary:'Auth token rotation — done.',                tokens:'212k', cost:'$0.74', dur:'32:09' },
];

const CHAT = [
  { who:'user', text:'The session router drops SSE messages when the client reconnects mid-stream. Investigate.' },
  { who:'claude', text:"Reading the router to see how it buffers messages between connections." },
  { who:'tool', name:'read_file', arg:'src/server/sessions/router.ts', meta:'142 lines' },
  { who:'claude', text:'The buffer is keyed on socket id, not session id — that\'s why a reconnect loses everything. Switching to a per-session ring buffer.' },
  { who:'tool', name:'edit_file', arg:'src/server/sessions/router.ts', meta:'+18 −7', diff:true },
  { who:'tool', name:'run_bash',  arg:'pnpm test --filter=core', meta:'running…', running:true },
];

const DIFF_LINES = [
  { t:'h', s:'@@ -34,9 +34,12 @@' },
  { t:' ', s:'  export function makeRouter(opts: RouterOpts) {' },
  { t:'-', s:'    const buffers = new Map<SocketId, Msg[]>()' },
  { t:'+', s:'    const buffers = new Map<SessionId, RingBuffer<Msg>>()' },
  { t:'+', s:'    const subs    = new Map<SessionId, Set<Socket>>()' },
  { t:' ', s:'    const stream = new EventEmitter()' },
  { t:'-', s:'    socket.on("close", () => buffers.delete(socket.id))' },
  { t:'+', s:'    socket.on("close", () => unsub(socket))' },
];

Object.assign(window, {
  STATES, StateDot, StatePill, GitMark, ProviderBadge,
  Phone, Desk, Avatar, Spark,
  PROJECTS, SESSIONS, CHAT, DIFF_LINES,
});
