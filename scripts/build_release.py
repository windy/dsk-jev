"""Build dependency-free release archives and SHA256SUMS; no credentials required."""
import argparse,hashlib,os,re,subprocess,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('version');p.add_argument('--output',default='dist');args=p.parse_args()
 if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',args.version):raise SystemExit('Expected a version such as v0.1.0')
 dest=Path(args.output).resolve();dest.mkdir(parents=True,exist_ok=True);sums=[]
 for system in ('linux','darwin'):
  for arch in ('amd64','arm64'):
   name=f'dsk-jev_{args.version}_{system}_{arch}'
   with tempfile.TemporaryDirectory(prefix='dsk-jev-release-') as tmp:
    binary=Path(tmp)/'dsk-jev'
    subprocess.run(['go','build','-trimpath','-ldflags=-s -w','-o',str(binary),'./cmd/server'],cwd=ROOT,env=dict(os.environ,CGO_ENABLED='0',GOOS=system,GOARCH=arch),check=True)
    archive=dest/f'{name}.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
     tar.add(binary,arcname=f'{name}/dsk-jev')
     for path in ('README.md','README.zh-CN.md','LICENSE','THIRD_PARTY_NOTICES','CHANGELOG.md','.env.example','SECURITY.md','CONTRIBUTING.md','docs','examples','config','reports'):
      tar.add(ROOT/path,arcname=f'{name}/{path}')
    sums.append(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}')
    print(archive.name,flush=True)
 (dest/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
if __name__=='__main__':main()
