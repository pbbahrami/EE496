import subprocess
import threading
import shutil
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, request
import serial
import serial.tools.list_ports


ROOT = Path(__file__).resolve().parent
MIDI_DIR = ROOT / "midi_library"
SONG_DATA_DIR = ROOT / "song_data_library"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


class SerialBridge:
    def __init__(self) -> None:
        self.ser = None
        self.lock = threading.Lock()
        self.lines = deque(maxlen=300)
        self.status = {}
        self._thread = None
        self._running = False

    def connect(self, port: str, baud: int = 115200) -> None:
        self.disconnect()
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def disconnect(self) -> None:
        self._running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    def send(self, line: str) -> None:
        if not self.ser:
            raise RuntimeError("Not connected")
        self.ser.write((line.strip() + "\n").encode("utf-8"))

    def _reader_loop(self) -> None:
        while self._running and self.ser:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                with self.lock:
                    self.lines.append(line)
                    self._parse_status(line)
            except Exception:
                break

    def _parse_status(self, line: str) -> None:
        # Parses "k=v k=v" telemetry lines from firmware STATUS output.
        tokens = line.split()
        parsed = {}
        for t in tokens:
            if "=" not in t:
                continue
            k, v = t.split("=", 1)
            parsed[k] = v
        if parsed:
            self.status.update(parsed)

    def snapshot(self) -> dict:
        with self.lock:
            return {"connected": self.ser is not None, "status": dict(self.status), "lines": list(self.lines)}


bridge = SerialBridge()
app = Flask(__name__)


HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Teensy Companion</title>
  <style>
    :root{
      --bg:#070b16;--bg2:#0a1122;--card:#101a33;--cardEdge:#243a67;--text:#eef4ff;
      --muted:#9bb1d9;--accent:#79a9ff;--ok:#48dc98;--warn:#ffc15d;--danger:#ff7f7f;
      --glow:0 10px 30px rgba(0,0,0,.32);
    }
    *{box-sizing:border-box}
    body{
      margin:0;color:var(--text);font-family:Inter,system-ui,Segoe UI,Roboto,sans-serif;
      background:radial-gradient(1200px 700px at 20% -10%,#1a2d55 0%,transparent 60%),linear-gradient(180deg,var(--bg),var(--bg2));
    }
    .wrap{max-width:1180px;margin:28px auto;padding:0 16px 20px}
    h1{margin:0;font-size:30px;letter-spacing:.2px}
    .sub{color:var(--muted);margin:8px 0 18px}
    .grid{display:grid;gap:14px;grid-template-columns:repeat(12,minmax(0,1fr))}
    .card{
      background:linear-gradient(180deg,#101b35,#0f1a32);border:1px solid var(--cardEdge);
      border-radius:16px;padding:14px;box-shadow:var(--glow)
    }
    .title{font-weight:700;margin-bottom:10px}
    .span4{grid-column:span 4}.span6{grid-column:span 6}.span8{grid-column:span 8}.span12{grid-column:1/-1}
    @media(max-width:980px){.span4,.span6,.span8{grid-column:1/-1}}
    .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
    label{font-size:12px;letter-spacing:.2px;color:var(--muted)}
    select,input,button{
      border-radius:11px;border:1px solid #33538f;background:#0e1730;color:var(--text);padding:8px 11px
    }
    input[type=range]{padding:0;border:0;background:transparent;min-width:240px}
    input[type=color]{padding:0;width:54px;height:34px}
    button{cursor:pointer}
    .primary{background:var(--accent);color:#07142e;border-color:#8ab5ff;font-weight:700}
    .good{background:var(--ok);color:#072115;border-color:#68f5b3;font-weight:700}
    .warn{background:var(--warn);color:#332000;border-color:#ffd285;font-weight:700}
    .danger{background:var(--danger);color:#330505;border-color:#ff9a9a;font-weight:700}
    .pill{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700}
    .connected{background:#143d2d;color:#a7f4ce}
    .disconnected{background:#412020;color:#ffc0c0}
    .kv{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px}
    @media(max-width:980px){.kv{grid-template-columns:repeat(2,minmax(120px,1fr))}}
    .kv div{background:#0d1730;border:1px solid #28457c;border-radius:10px;padding:8px}
    .kv b{display:block;font-size:11px;color:var(--muted);margin-bottom:3px}
    #statusMsg{background:#0b1328;border:1px solid #274275;border-radius:10px;padding:10px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;min-height:48px}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Teensy Music Companion</h1>
    <div class="sub">Clean control panel for playback, songs, and visual settings.</div>
    <div class="grid">
      <div class="card span6">
        <div class="title">Connection</div>
        <div class="row">
          <label>Port</label>
          <select id="port"></select>
          <button onclick="refreshPorts()">Refresh</button>
          <button class="good" onclick="connectPort()">Connect</button>
          <button class="danger" onclick="disconnectPort()">Disconnect</button>
          <span id="connBadge" class="pill disconnected">Disconnected</span>
        </div>
      </div>

      <div class="card span6">
        <div class="title">Transport</div>
        <div class="row">
          <button class="primary" onclick="cmd('PLAY')">Play</button>
          <button class="warn" onclick="cmd('PAUSE')">Pause</button>
          <button class="danger" onclick="cmd('STOP')">Stop</button>
          <button onclick="cmd('STATUS')">Refresh Status</button>
        </div>
        <div class="row">
          <label>Song Position</label>
          <input id="seek" type="range" min="0" max="1000" value="0" oninput="onSeekInput(this.value)" onchange="onSeekCommit(this.value)">
          <span id="seekv">0.0s</span>
        </div>
        <div class="row">
          <label>BPM</label>
          <input id="bpm" type="range" min="40" max="260" value="120" oninput="setBpm(this.value)">
          <span id="bpmv">120</span>
        </div>
        <div class="row">
          <label>Brightness</label>
          <input id="bri" type="range" min="0" max="255" value="35" oninput="setBrightness(this.value)">
          <span id="briv">35</span>
        </div>
      </div>

      <div class="card span8">
        <div class="title">Visuals</div>
        <div class="row">
          <label>Color Mode</label>
          <select id="colorMode" onchange="cmd('MODE '+this.value)">
            <option>fixed</option><option>pitch</option><option>rainbow</option><option>alternate</option>
          </select>
          <label>Play Mode</label>
          <select id="playMode" onchange="cmd('PMODE '+this.value)">
            <option>continuous</option><option>guided</option>
          </select>
        </div>
        <div class="row">
          <label>Base Color Wheel</label>
          <input id="picker" type="color" value="#206ee6" onchange="setBaseFromPicker(this.value)">
          <span id="statusMsg">Ready</span>
        </div>
      </div>

      <div class="card span4">
        <div class="title">Onboard Songs</div>
        <div class="row">
          <select id="onboardSong" style="min-width:230px">
            <option value="0">Bohemian Rhapsody</option>
            <option value="1">Get Lucky</option>
            <option value="2">Imagine</option>
            <option value="3">Wheels on the Bus</option>
            <option value="4">Fur Elise</option>
            <option value="5">Super Mario 64 Medley</option>
            <option value="6">Super Mario Bros Main Theme</option>
            <option value="7">The Entertainer</option>
            <option value="8">Wii Mii Channel</option>
            <option value="9">Twinkle Twinkle Little Star</option>
            <option value="10">Stairway to Heaven</option>
          </select>
          <button class="primary" onclick="selectOnboardSong(onboardSong.value)">Load</button>
        </div>
        <div id="fwSongHint" style="margin-top:8px;font-size:12px;color:var(--warn)"></div>
        <div style="color:var(--muted);font-size:12px">Songs are compiled into firmware. Use latest <code>web_companion.py</code> so this list matches <code>song_count</code> in Live Status.</div>
      </div>

      <div class="card span12">
        <div class="title">Live Status</div>
        <div class="kv" id="statusKv"></div>
      </div>
    </div>
  </div>
  <script>
    const seek = document.getElementById('seek');
    const seekv = document.getElementById('seekv');
    const statusMsg = document.getElementById('statusMsg');
    let seekDragging = false;
    let seekIgnoreUntilMs = 0;

    seek.addEventListener('pointerdown',()=>{seekDragging=true;});
    seek.addEventListener('pointerup',()=>{seekDragging=false;});
    seek.addEventListener('touchstart',()=>{seekDragging=true;},{passive:true});
    seek.addEventListener('touchend',()=>{seekDragging=false;},{passive:true});

    async function jget(u){return (await fetch(u)).json();}
    async function jpost(u,obj){return (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj||{})})).json();}
    async function refreshPorts(){
      const d=await jget('/api/ports');
      const s=port; s.innerHTML='';
      d.ports.forEach(p=>{const o=document.createElement('option');o.text=o.value=p;s.add(o);});
    }
    async function connectPort(){await jpost('/api/connect',{port:port.value}); statusMsg.textContent='Connected';}
    async function disconnectPort(){await jpost('/api/disconnect',{}); statusMsg.textContent='Disconnected';}
    async function cmd(c){await jpost('/api/cmd',{cmd:c});}

    function setBpm(v){bpmv.textContent=v;cmd('BPM '+v);}
    function setBrightness(v){briv.textContent=v;cmd('BRI '+v);}
    function setBaseFromPicker(hex){
      const v=hex.replace('#','');
      const r=parseInt(v.slice(0,2),16), g=parseInt(v.slice(2,4),16), b=parseInt(v.slice(4,6),16);
      cmd(`BASE ${r} ${g} ${b}`);
      statusMsg.textContent=`Base color set to ${hex.toUpperCase()}`;
    }
    function onSeekInput(v){seekv.textContent=(v/1000).toFixed(1)+'s';}
    function onSeekCommit(v){
      const ms=parseInt(v,10);
      if(ms<=30){cmd('STOP'); return;}
      seekIgnoreUntilMs=Date.now()+450;
      cmd('SEEKMS '+ms);
      statusMsg.textContent=`Seek ${ (ms/1000).toFixed(1) }s`;
    }
    async function selectOnboardSong(idx){
      await cmd('SONG '+idx);
      statusMsg.textContent='Loaded song index '+idx;
    }
    function renderStatus(status){
      const entries=Object.entries(status||{});
      if(!entries.length){statusKv.innerHTML='';return;}
      statusKv.innerHTML=entries.map(([k,v])=>`<div><b>${k}</b>${v}</div>`).join('');
    }
    async function poll(){
      const d=await jget('/api/snapshot');
      connBadge.textContent=d.connected?'Connected':'Disconnected';
      connBadge.className='pill '+(d.connected?'connected':'disconnected');
      renderStatus(d.status);
      const len=parseInt(d.status.length_ms||'0',10);
      const t=parseInt(d.status.time_ms||'0',10);
      if(len>0){seek.max=len;}
      if(!seekDragging && Date.now()>seekIgnoreUntilMs && t>=0){
        seek.value=t;
        seekv.textContent=(t/1000).toFixed(1)+'s';
      }
      const sc=parseInt(d.status.song_count||'0',10);
      const listed=document.getElementById('onboardSong').options.length;
      const hint=document.getElementById('fwSongHint');
      if(sc>0 && sc!==listed){
        hint.textContent=`Firmware reports ${sc} songs but this page lists ${listed}. Git pull, restart this app (stop Python and run again), hard-refresh browser (⌘⇧R).`;
      }else{
        hint.textContent='';
      }
    }
    setInterval(poll,600);
    setInterval(()=>cmd('STATUS'),1500);
    refreshPorts();
    setBaseFromPicker(document.getElementById('picker').value);
  </script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML


@app.route("/api/ports")
def ports():
    return jsonify({"ports": [p.device for p in serial.tools.list_ports.comports()]})


@app.route("/api/connect", methods=["POST"])
def connect():
    data = request.get_json(force=True)
    bridge.connect(data["port"], int(data.get("baud", 115200)))
    return jsonify({"ok": True})


@app.route("/api/disconnect", methods=["POST"])
def disconnect():
    bridge.disconnect()
    return jsonify({"ok": True})


@app.route("/api/cmd", methods=["POST"])
def cmd():
    data = request.get_json(force=True)
    bridge.send(data["cmd"])
    return jsonify({"ok": True})


@app.route("/api/snapshot")
def snapshot():
    snap = bridge.snapshot()
    return jsonify(snap)


@app.route("/api/midi-files")
def midi_files():
    MIDI_DIR.mkdir(exist_ok=True)
    files = sorted([p.name for p in MIDI_DIR.iterdir() if p.suffix.lower() in (".mid", ".midi")])
    return jsonify({"files": files})


@app.route("/api/midi-tracks")
def midi_tracks():
    midi_name = request.args.get("file", "")
    midi_path = MIDI_DIR / midi_name
    if not midi_path.exists():
        return jsonify({"error": f"Missing file: {midi_name}"}), 400

    py = str(VENV_PYTHON if VENV_PYTHON.exists() else "python3")
    probe = (
        "import mido, json, sys;"
        "mid=mido.MidiFile(sys.argv[1]);"
        "print(json.dumps([{'index':i,'name':(t.name or '').strip(),'events':len(t)} for i,t in enumerate(mid.tracks)]))"
    )
    p = subprocess.run([py, "-c", probe, str(midi_path)], cwd=str(ROOT), capture_output=True, text=True)
    if p.returncode != 0:
        return jsonify({"error": (p.stdout + "\n" + p.stderr).strip()}), 500
    try:
        data = __import__("json").loads(p.stdout.strip() or "[]")
    except Exception:
        data = []
    return jsonify({"tracks": data})


@app.route("/api/song-data-files")
def song_data_files():
    SONG_DATA_DIR.mkdir(exist_ok=True)
    files = sorted([p.name for p in SONG_DATA_DIR.iterdir() if p.suffix.lower() == ".h"])
    return jsonify({"files": files})


@app.route("/api/build-song-data", methods=["POST"])
def build_song_data():
    data = request.get_json(force=True)
    midi_name = data.get("file", "")
    track = int(data.get("track", 3))
    midi_path = MIDI_DIR / midi_name
    if not midi_path.exists():
        return jsonify({"error": f"Missing file: {midi_name}"}), 400
    SONG_DATA_DIR.mkdir(exist_ok=True)
    out_name = midi_path.stem + ".h"
    out_path = SONG_DATA_DIR / out_name
    py = str(VENV_PYTHON if VENV_PYTHON.exists() else "python3")
    cmd = [
        py,
        str(ROOT / "miditoteensy.py"),
        "--midi",
        str(midi_path),
        "--track",
        str(track),
        "--out",
        str(out_path),
    ]
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    ok = p.returncode == 0
    output = (p.stdout + "\n" + p.stderr).strip()
    if ok:
        output = (output + f"\nSaved: {out_name}").strip()
    return jsonify({"ok": ok, "output": output})


@app.route("/api/activate-song-data", methods=["POST"])
def activate_song_data():
    data = request.get_json(force=True)
    file_name = data.get("file", "")
    src = SONG_DATA_DIR / file_name
    if not src.exists():
        return jsonify({"error": f"Missing song data: {file_name}"}), 400
    dst = ROOT / "src" / "song_data.h"
    shutil.copy(src, dst)
    return jsonify({"ok": True, "output": f"Activated {file_name} -> src/song_data.h"})


@app.route("/api/upload", methods=["POST"])
def upload():
    p = subprocess.run(
        ["pio", "run", "-e", "teensy41", "-t", "upload"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return jsonify({"ok": p.returncode == 0, "output": (p.stdout + "\n" + p.stderr).strip()})


if __name__ == "__main__":
    print("Open http://127.0.0.1:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)
