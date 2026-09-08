import hashlib,json,lzma,resource,sys,tempfile,time
from pathlib import Path
source=Path(sys.argv[1]); level=int(sys.argv[2]); remaining=int(sys.argv[3])*1024*1024 if len(sys.argv)>3 else 16*1024*1024; size=0; expected=hashlib.sha256(); start=time.monotonic()
with tempfile.TemporaryDirectory(prefix='archive-bench-') as work:
 target=Path(work)/'sample.xz'
 with source.open('rb') as src,lzma.open(target,'wb',preset=level,check=lzma.CHECK_CRC64) as dest:
  while remaining:
   block=src.read(min(4*1024*1024,remaining))
   if not block:break
   dest.write(block); expected.update(block); size+=len(block);remaining-=len(block)
 elapsed=time.monotonic()-start; compressed=target.stat().st_size; digest=hashlib.sha256()
 with lzma.open(target,'rb') as src:
  for block in iter(lambda:src.read(4*1024*1024),b''):digest.update(block)
 assert digest.digest()==expected.digest()
 print(json.dumps(dict(level=level,input_bytes=size,compressed_bytes=compressed,seconds=round(elapsed,3),max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,verified=True)))
