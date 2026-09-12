"""Real Android screenrecord segments, with a playback copy and capture timeline."""
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from amazon_cart_001.harness.evidence import save, digest, stamp
from amazon_cart_001.harness.device import Device

class ScreenRecording:
    def __init__(self,device,root,episode,ffmpeg):
        # Recording runs concurrently: never share the actor's phase or trace.
        self.device = Device(device.serial, device.adb)
        self.device.phase = "recording"
        self.root,self.episode,self.ffmpeg=Path(root),episode,ffmpeg
        self.directory=self.root/"video"; self.directory.mkdir()
        self.stop_event=threading.Event(); self.ready=threading.Event()
        self.segments=[]; self.errors=[]; self.thread=None; self.pid=None
        self.started=None; self.stopped=None
        self.resolution=None

    def start(self):
        png=(self.root/"frames"/"000"/"screen.png").read_bytes()
        width,height=int.from_bytes(png[16:20],"big"),int.from_bytes(png[20:24],"big")
        self.resolution="540x"+str(round(540*height/width/2)*2)
        self.started=stamp()
        self.thread=threading.Thread(target=self._capture,name="peach-screenrecord",daemon=False)
        self.thread.start()
        if not self.ready.wait(15) or self.errors:
            self.stop()
            raise RuntimeError("Screen recording failed to start: "+str(self.errors))

    def _capture(self):
        index=0
        while not self.stop_event.is_set():
            remote="/sdcard/"+self.episode+"-"+str(index)+".mp4"
            local=self.directory/f"segment-{index:03d}.mp4"
            entry={"index":index,"started_at":stamp(),"started_monotonic":time.monotonic(),"path":str(local.relative_to(self.root))}
            proc=None
            try:
                # The printed PID becomes screenrecord via exec, so shutdown targets
                # exactly our process, never all recorders or other emulator sessions.
                command="echo $$; exec screenrecord --size "+self.resolution+" --bit-rate 1200000 --time-limit 175 "+remote
                proc=subprocess.Popen([self.device.adb,"-s",self.device.serial,"shell","sh","-c",
                    "'"+command+"'"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                line=proc.stdout.readline().strip()
                if not line.isdigit(): raise RuntimeError("Missing recorder PID: "+line)
                self.pid=int(line)
                time.sleep(0.5)
                if proc.poll() is not None: raise RuntimeError("Recorder exited: "+proc.stderr.read()[:1000])
                entry["pid"]=self.pid
                self.ready.set()
                while proc.poll() is None and not self.stop_event.wait(0.2): pass
                if proc.poll() is None:
                    self.device.command("shell","kill","-2",str(self.pid))
                stdout,stderr=proc.communicate(timeout=15)
                entry.update(stopped_at=stamp(),stopped_monotonic=time.monotonic(),
                    returncode=proc.returncode,stderr=stderr[:2000])
                data=self.device.command("exec-out","cat",remote,timeout=45)
                if len(data)<1000 or b"ftyp" not in data[:40]: raise RuntimeError("Invalid screenrecord MP4")
                local.write_bytes(data)
                entry.update(bytes=len(data),sha256=digest(data))
                self.segments.append(entry)
                self.device.command("shell","rm","-f",remote)
                self.pid=None
                save(self.directory/"recording.json",self.receipt())
                index+=1
            except Exception as error:
                self.errors.append(type(error).__name__+": "+str(error))
                self.stop_event.set()
                self.ready.set()
                if proc is not None and proc.poll() is None:
                    try:
                        if self.pid: self.device.command("shell","kill","-2",str(self.pid))
                        proc.wait(timeout=15)
                    except Exception:
                        proc.terminate()
                break

    def receipt(self):
        return {"source":"Android screenrecord, not a screenshot slideshow",
            "started_at":self.started,"stopped_at":self.stopped,"segments":self.segments,
            "errors":self.errors,"segment_limit_seconds":175,"resolution":self.resolution,
            "command_trace":list(self.device.trace), "command_trace_scope":"recording_only",
            "continuous_claim":False,"boundary_note":"Long runs rotate real recordings; wall-clock gaps between segments remain recorded."}

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=65)
        if self.thread and self.thread.is_alive():
            self.errors.append("Recorder did not finish within shutdown deadline")
            raise RuntimeError(self.errors[-1])
        self.stopped=stamp()
        receipt=self.receipt()
        if self.segments:
            listing=self.directory/"segments.txt"
            listing.write_text("".join("file '"+Path(s["path"]).name+"'\n" for s in self.segments))
            destination=self.directory/"screen-recording.mp4"
            result=subprocess.run([self.ffmpeg,"-nostdin","-hide_banner","-y","-f","concat","-safe","1",
                "-i",str(listing),"-an","-vf","fps=10","-c:v","libx264","-preset","veryfast",
                "-crf","31","-pix_fmt","yuv420p","-movflags","+faststart",str(destination)],
                capture_output=True,text=True,timeout=120)
            (self.directory/"encode.log").write_text(result.stderr)
            result.check_returncode()
            data=destination.read_bytes()
            receipt["playback"]={"path":str(destination.relative_to(self.root)),"bytes":len(data),"sha256":digest(data),
                "mime_type":"video/mp4","encoding":"H.264, 10 fps; timestamps retained within each segment"}
        save(self.directory/"recording.json",receipt)
        return receipt
