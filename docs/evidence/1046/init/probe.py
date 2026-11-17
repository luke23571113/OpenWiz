"""One disk journal stall during the final apply of the lost-label case."""
import importlib.util, json, pathlib, subprocess, sys, unittest
root=pathlib.Path.cwd()
spec=importlib.util.spec_from_file_location('test_init', root/'tools/install/tests/init/test_init.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
class Probe(t.Init):
 def test_lost_label(self):
  self.world({t.CODE.lower():t.repository(t.CODE,'public')},faults=[{'method':'POST','path':f'repos/{t.CODE}/labels','mode':'lose','times':1}])
  preview=self.init()
  self.assertEqual(self.apply(preview,expect=6)['outcome'],'uncertain')
  count=len(self.writes())
  self.assertEqual(self.init(expect=6)['operation_id'],preview['operation_id'])
  self.assertEqual(len(self.writes()),count)
  wrapper=self.base/'stall.py'
  wrapper.write_text('''import os, runpy, sys, time
original=os.fsync
held=False
def stall(fd):
 global held
 path=os.readlink('/proc/self/fd/'+str(fd))
 if not held and path.startswith('/tmp/openwiz-init-test-'):
  held=True
  print('probe: disk-backed journal wait injected',file=sys.stderr,flush=True)
  time.sleep(61)
 return original(fd)
os.fsync=stall
sys.argv[0]=sys.argv[1];del sys.argv[1]
runpy.run_path(sys.argv[0],run_name='__main__')
''')
  original=t.subprocess.run
  def run(argv,**kw):
   if str(t.INIT) in argv: argv=[*argv[:2],str(wrapper),*argv[2:]]
   return original(argv,**kw)
  t.subprocess.run=run
  try: done=self.apply(preview)
  finally:t.subprocess.run=original
  self.assertEqual(done['outcome'],'applied')
  self.assertEqual(self.read()['repos'][t.CODE.lower()]['labels'],['openwiz'])
  self.assertEqual(len(self.read()['repos'][t.COMPANION.lower()]['pulls']),1)
unittest.main(argv=['probe','Probe.test_lost_label'],verbosity=2)
