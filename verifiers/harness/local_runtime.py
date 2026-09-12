"""Isolated local KVM readiness check. Never calls a model or submits an eval."""
import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from amazon_cart_001.harness.peach import PeachDevice
from amazon_cart_001.harness.recording import ScreenRecording
from amazon_cart_001.integrations.live_viewer import LiveViewer
from amazon_cart_001.verification.strict import rubric_identity

TASK_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = TASK_ROOT / "artifacts/local_kvm"
PORTS = (5048, 5584, 5585, 8578)


def require_local_output(path):
    path = Path(path).resolve()
    if not path.is_relative_to(OUTPUT.resolve()):
        raise ValueError("Runtime output must stay in this task's artifacts/local_kvm")
    if not path.is_relative_to(Path('/data/Tirtha')):
        raise ValueError("This launcher only writes under /data/Tirtha")
    return path


def require_free_ports(ports=PORTS):
    reservations = []
    try:
        for port in ports:
            sock = socket.socket()
            reservations.append(sock)
            sock.bind(('127.0.0.1', port))
    except OSError as exc:
        raise RuntimeError("Dedicated local port is occupied; no existing service will be stopped") from exc
    finally:
        for sock in reservations:
            sock.close()


def stop_owned(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


class LocalRuntime:
    def __init__(self, sdk, java, ffmpeg, output=OUTPUT):
        self.output = require_local_output(output)
        self.sdk, self.java, self.ffmpeg = Path(sdk).resolve(), Path(java).resolve(), Path(ffmpeg).resolve()
        for tool in (self.sdk/'emulator/emulator', self.sdk/'platform-tools/adb',
                     self.sdk/'cmdline-tools/latest/bin/avdmanager', self.java/'bin/java', self.ffmpeg):
            if not tool.is_file() or not os.access(tool, os.X_OK):
                raise ValueError('Required executable unavailable: ' + str(tool))
        self.root = self.work = None
        self.adb_process = self.emulator = self.viewer = self.recorder = None
        self.recording_started = False
        self.previous_env = {}
        self.report = {'kind':'local_kvm_readiness', 'evaluation':False, 'status':'STARTING',
                       'reward':None, 'model_calls':0, 'task_actions':0,
                       'execution_location':'local-server-kvm', 'prime_hosted':False,
                       'strict_rubric':rubric_identity(), 'cleanup':{}}

    def save(self):
        if self.root:
            (self.root/'readiness.json').write_text(json.dumps(self.report, indent=2))

    def command(self, args, timeout=60, input=None):
        result = subprocess.run(list(map(str,args)), input=input, capture_output=True, text=True, timeout=timeout)
        with (self.root/'runtime.jsonl').open('a') as log:
            log.write(json.dumps({'argv':list(map(str,args)), 'exit_code':result.returncode,
                                 'stdout':result.stdout, 'stderr':result.stderr})+'\n')
        result.check_returncode()
        return result.stdout

    def configure(self):
        require_free_ports()
        if not Path('/dev/kvm').is_char_device() or not os.access('/dev/kvm',os.R_OK|os.W_OK):
            raise RuntimeError('KVM_UNAVAILABLE: no software-emulation fallback')
        self.output.mkdir(parents=True,exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%dT%H%M%SZ_',time.gmtime()),dir=self.output))
        self.work = Path(tempfile.mkdtemp(prefix='runtime.',dir=self.root))
        for name in ('tmp','android-user','avd','xdg-cache','xdg-config','xdg-data','xdg-runtime'):
            (self.work/name).mkdir(mode=0o700)
        settings = {'ANDROID_HOME':str(self.sdk),'ANDROID_SDK_ROOT':str(self.sdk),'JAVA_HOME':str(self.java),
            'PATH':str(self.java/'bin')+':'+str(self.sdk/'platform-tools')+':'+os.environ.get('PATH',''),
            'ANDROID_AVD_HOME':str(self.work/'avd'),'ANDROID_USER_HOME':str(self.work/'android-user'),
            'ANDROID_EMULATOR_HOME':str(self.work/'android-user'),
            'ANDROID_ADB_SERVER_PORT':str(PORTS[0]),'ADB_SERVER_SOCKET':f'tcp:127.0.0.1:{PORTS[0]}',
            'ADB_VENDOR_KEYS':str(self.work/'android-user/adbkey'),
            'TMPDIR':str(self.work/'tmp'),'TMP':str(self.work/'tmp'),'TEMP':str(self.work/'tmp'),
            'XDG_CACHE_HOME':str(self.work/'xdg-cache'),'XDG_CONFIG_HOME':str(self.work/'xdg-config'),
            'XDG_DATA_HOME':str(self.work/'xdg-data'),'XDG_RUNTIME_DIR':str(self.work/'xdg-runtime'),
            'JAVA_TOOL_OPTIONS':f'-Duser.home={self.work}/android-user -Djava.io.tmpdir={self.work}/tmp'}
        self.previous_env = {k:os.environ.get(k) for k in (*settings, 'ANDROID_SDK_HOME', 'ANDROID_PREFS_ROOT')}
        # Legacy preference-root variables conflict with ANDROID_USER_HOME.
        os.environ.pop('ANDROID_SDK_HOME',None)
        os.environ.pop('ANDROID_PREFS_ROOT',None)
        os.environ.update(settings)
        self.report.update(run_dir=str(self.root), serial=f'emulator-{PORTS[1]}', adb_port=PORTS[0],
                           installed_tools={'sdk':str(self.sdk),'java':str(self.java),'ffmpeg':str(self.ffmpeg)})
        print('READINESS_DIR='+str(self.root),flush=True)
        self.save()

    def start(self):
        self.configure()
        emulator, adb = self.sdk/'emulator/emulator', self.sdk/'platform-tools/adb'
        acceleration = self.command([emulator,'-accel-check'])
        if 'KVM' not in acceleration or 'usable' not in acceleration:
            raise RuntimeError('Emulator did not confirm usable KVM')
        self.report['kvm_check'] = acceleration.strip()
        self.report['emulator_version'] = self.command([emulator,'-version']).splitlines()[0]
        self.command([self.ffmpeg,'-version'])
        # Rebuild current Java/XML resources; no stale APK or shared SDK writes.
        self.command(['bash',TASK_ROOT/'app/amazon_android_ui/build_apk.sh'],timeout=180)
        apk = TASK_ROOT/'app/amazon_android_ui/build/out/democart-ui.apk'
        self.command([self.sdk/'cmdline-tools/latest/bin/avdmanager','create','avd',
            '--name','DemoCartLocal','--package','system-images;android-33;google_apis;x86_64',
            '--path',self.work/'avd/device','--device','pixel_6'],input='no\n')
        self.command([adb,'keygen',self.work/'android-user/adbkey'])
        with (self.root/'adb.log').open('wb') as log:
            self.adb_process = subprocess.Popen([str(adb),'-L',f'tcp:{PORTS[0]}','nodaemon','server'],stdout=log,stderr=log)
        for _ in range(30):
            if self.adb_process.poll() is not None:
                raise RuntimeError('Owned ADB server exited; see adb.log')
            try:
                with socket.create_connection(('127.0.0.1',PORTS[0]),timeout=0.2):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError('Owned ADB server did not listen')
        args = [str(emulator),'-avd','DemoCartLocal','-ports',f'{PORTS[1]},{PORTS[2]}',
            '-grpc',str(PORTS[3]),'-grpc-use-jwt','-no-window','-no-audio','-no-snapshot',
            '-no-boot-anim','-accel','on','-gpu','swiftshader_indirect','-memory','4096','-cores','4',
            '-no-metrics']
        with (self.root/'emulator.log').open('wb') as log:
            self.emulator = subprocess.Popen(args,stdout=log,stderr=log)
        deadline = time.monotonic()+240
        last_boot_log = 0
        while time.monotonic()<deadline:
            if self.emulator.poll() is not None:
                raise RuntimeError('Emulator exited; inspect emulator.log')
            boot = subprocess.run([str(adb),'-s',self.report['serial'],'shell','getprop','sys.boot_completed'],
                                  capture_output=True,text=True,timeout=10)
            if time.monotonic()-last_boot_log>15:
                with (self.root/'boot.jsonl').open('a') as log:
                    log.write(json.dumps({'stdout':boot.stdout,'stderr':boot.stderr,'exit_code':boot.returncode})+'\n')
                last_boot_log=time.monotonic()
            if boot.stdout.strip()=='1':
                break
            time.sleep(2)
        else:
            raise RuntimeError('Android boot deadline exceeded')
        self.command([adb,'-s',self.report['serial'],'shell','input','keyevent','82'])
        self.command([adb,'-s',self.report['serial'],'install','-r',apk])
        self.device = PeachDevice(self.report['serial'],str(adb))
        self.episode = 'peach_'+uuid4().hex
        self.report['installed_apk'] = self.device.installed(apk)
        self.device.start(self.episode)
        frame = self.device.capture(self.root,0,self.episode)
        session = frame['tables']['eval_session']
        if len(session)!=1 or session[0]['page']!='home' or frame['tables']['cart'] or frame['tables']['search_history']:
            raise RuntimeError('Readiness app state is not a clean home screen')
        self.report.update(episode_id=self.episode, initial_evidence_stable=True,
            screenshot=str(self.root/'frames/000/screen.png'),
            visible_targets=sorted({n['id'] for n in frame['ui'] if n['id']}))
        self.recorder = ScreenRecording(self.device,self.root,self.episode,str(self.ffmpeg))
        self.recorder.start()
        self.recording_started = True
        self.viewer = LiveViewer(self.capture,public_readonly=True,local_readiness=True,label='DemoCart · local KVM · NOT AN EVALUATION')
        port = self.viewer.start_local()
        if not self.viewer.status()['connected']:
            raise RuntimeError('Viewer has no fresh Android image')
        self.report.update(status='READY',viewer_url=f'http://127.0.0.1:{port}',viewer_scope='loopback_only_read_only')
        self.save()
        print(json.dumps({'status':'READY','viewer_url':self.report['viewer_url'],
                          'screenshot':self.report['screenshot'],'evaluation':False}),flush=True)

    def capture(self):
        png = self.device.command('exec-out','screencap','-p',timeout=10)
        return {'frame_id':uuid4().hex,'sha256':hashlib.sha256(png).hexdigest(),
                'width':int.from_bytes(png[16:20],'big'),'height':int.from_bytes(png[20:24],'big'),
                'episode_id':self.episode,'interactive':False},png

    def close(self):
        errors=[]
        if self.viewer:
            try:
                self.viewer.stop_local()
            except Exception as exc:
                errors.append('viewer: '+str(exc))
        if self.recording_started:
            try:
                recording=self.recorder.stop()
                self.report['recording']=recording
                if recording.get('errors') or not recording.get('playback'):
                    raise RuntimeError('Recording did not export correctly')
                video=self.root/recording['playback']['path']
                self.command([self.ffmpeg,'-v','error','-i',video,'-f','null','-'],timeout=30)
                self.report['recording_decode_verified']=True
            except Exception as exc:
                errors.append('recording: '+str(exc))
        for name,process in (('emulator',self.emulator),('adb',self.adb_process)):
            try:
                stop_owned(process)
                self.report['cleanup'][name+'_stopped']=process is None or process.poll() is not None
            except Exception as exc:
                errors.append(name+': '+str(exc))
        # Only the exact temporary directory created by configure is disposable.
        if self.work and self.work.parent==self.root and self.work.name.startswith('runtime.') and not self.work.is_symlink():
            if not errors:
                try:
                    shutil.rmtree(self.work)
                    self.report['cleanup']['temporary_runtime_removed']=True
                except OSError as exc:
                    errors.append('temporary runtime cleanup: '+str(exc))
        for key,previous in self.previous_env.items():
            if previous is None:
                os.environ.pop(key,None)
            else:
                os.environ[key]=previous
        if errors:
            self.report.update(status='ERROR',cleanup_errors=errors)
        self.report['running']=False
        self.save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hold-seconds',type=int,default=5,help='Keep read-only UI open after boot, at most 900 seconds')
    args=parser.parse_args()
    if not 1<=args.hold_seconds<=900:
        parser.error('Hold must be between 1 and 900 seconds')
    runtime=LocalRuntime(os.environ['ANDROID_SDK_ROOT'],os.environ['JAVA_HOME'],os.environ['CART_FFMPEG'])
    def interrupted(signum,frame):
        raise KeyboardInterrupt
    previous=signal.signal(signal.SIGTERM,interrupted)
    try:
        runtime.start()
        time.sleep(args.hold_seconds)
    except (Exception,KeyboardInterrupt) as exc:
        runtime.report.update(status='ERROR',error=type(exc).__name__+': '+str(exc))
    finally:
        runtime.close()
        signal.signal(signal.SIGTERM,previous)
    print(json.dumps(runtime.report,indent=2),flush=True)
    return 0 if runtime.report['status']=='READY' else 1


if __name__=='__main__':
    raise SystemExit(main())

