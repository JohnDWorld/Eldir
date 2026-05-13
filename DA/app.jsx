// app.jsx — wires up the design canvas with all 5 directions

const SECTIONS = [
  { id:'d6', title:'Direction 6 · Cockpit + Cork board (D1 × D3)',
    subtitle:'Fast-read top strip from Mission Control, post-it kanban below — Past / Now / Next.',
    artboards:[
      ['d6-mh','Mobile · Board',         375,667, ()=><D6MobileHome/>],
      ['d6-ms','Mobile · Session board', 375,667, ()=><D6MobileSession/>],
      ['d6-dh','Desktop · Board',       1200,760, ()=><D6DeskHome/>],
      ['d6-ds','Desktop · Session',     1200,760, ()=><D6DeskSession/>],
    ]},
  { id:'d1', title:'Direction 1 · Mission Control', subtitle:'Cockpit / NASA control room — dense, multi-pane.',
    artboards:[
      ['d1-mh','Mobile · Home',          375,667, ()=><D1MobileHome/>],
      ['d1-ms','Mobile · Session',       375,667, ()=><D1MobileSession/>],
      ['d1-dh','Desktop · Home',        1200,760, ()=><D1DeskHome/>],
      ['d1-ds','Desktop · Session',     1200,760, ()=><D1DeskSession/>],
    ]},
  { id:'d2', title:'Direction 2 · Focus', subtitle:'Linear / Things 3 — one thing at a time, ⌘K everywhere.',
    artboards:[
      ['d2-mh','Mobile · Home',          375,667, ()=><D2MobileHome/>],
      ['d2-ms','Mobile · Session',       375,667, ()=><D2MobileSession/>],
      ['d2-dh','Desktop · Home + ⌘K',   1200,760, ()=><D2DeskHome/>],
      ['d2-ds','Desktop · Session',     1200,760, ()=><D2DeskSession/>],
    ]},
  { id:'d3', title:'Direction 3 · Workshop', subtitle:'Atelier — pegboard with tools, warm and tactile.',
    artboards:[
      ['d3-mh','Mobile · Home',          375,667, ()=><D3MobileHome/>],
      ['d3-ms','Mobile · Bench',         375,667, ()=><D3MobileSession/>],
      ['d3-dh','Desktop · Workshop',    1200,760, ()=><D3DeskHome/>],
      ['d3-ds','Desktop · At the bench',1200,760, ()=><D3DeskSession/>],
    ]},
  { id:'d4', title:'Direction 4 · Terminal-first', subtitle:'tmux / Warp — dense monospace, keyboard-led.',
    artboards:[
      ['d4-mh','Mobile · Home',          375,667, ()=><D4MobileHome/>],
      ['d4-ms','Mobile · Session',       375,667, ()=><D4MobileSession/>],
      ['d4-dh','Desktop · 4-pane',      1200,760, ()=><D4DeskHome/>],
      ['d4-ds','Desktop · Session',     1200,760, ()=><D4DeskSession/>],
    ]},
  { id:'d5', title:'Direction 5 · Conversation-led', subtitle:'Claude.ai — the chat IS the interface.',
    artboards:[
      ['d5-mh','Mobile · Home',          375,667, ()=><D5MobileHome/>],
      ['d5-ms','Mobile · Conversation',  375,667, ()=><D5MobileSession/>],
      ['d5-dh','Desktop · New chat',    1200,760, ()=><D5DeskHome/>],
      ['d5-ds','Desktop · Conversation',1200,760, ()=><D5DeskSession/>],
    ]},
];

function App() {
  return (
    <DesignCanvas>
      {SECTIONS.map(sec => (
        <DCSection key={sec.id} id={sec.id} title={sec.title} subtitle={sec.subtitle}>
          {sec.artboards.map(([id,label,w,h,Comp]) => (
            <DCArtboard key={id} id={id} label={label} width={w} height={h}>
              <Comp/>
            </DCArtboard>
          ))}
        </DCSection>
      ))}
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
