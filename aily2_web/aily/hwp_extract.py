"""Minimal HWP5 OLE compound parser and plain-text paragraph extractor.
Supports compressed BodyText Section streams; never executes macros or active content.
"""
import struct, zlib, re
EOC=0xfffffffe; FREE=0xffffffff

def u16(b,i): return struct.unpack_from('<H',b,i)[0]
def u32(b,i): return struct.unpack_from('<I',b,i)[0]
def u64(b,i): return struct.unpack_from('<Q',b,i)[0]
class Compound:
 def __init__(self,data):
  self.b=data
  if data[:8]!=bytes.fromhex('d0cf11e0a1b11ae1'): raise ValueError('not OLE HWP5')
  self.secsize=1<<u16(data,30); self.minisize=1<<u16(data,32); self.cutoff=u32(data,56)
  ids=[u32(data,76+i*4) for i in range(109)]; di=u32(data,68)
  for _ in range(u32(data,72)):
   sector=self.sector(di); ids += [u32(sector,j*4) for j in range(self.secsize//4-1)]; di=u32(sector,self.secsize-4)
  ids=[i for i in ids if i not in (FREE,EOC)][:u32(data,44)]
  self.fat=b''.join(self.sector(i) for i in ids)
  directory=self.chain(u32(data,48))
  self.items=[]
  for j in range(0,len(directory),128):
   x=directory[j:j+128]
   if len(x)<128: break
   length=u16(x,64)
   name=x[:max(0,length-2)].decode('utf-16le','replace') if length else ''
   self.items.append({'name':name,'type':x[66], 'left':u32(x,68),'right':u32(x,72),'child':u32(x,76),'start':u32(x,116),'size':u64(x,120)})
  self.root=self.items[0]
  self.ministream=self.chain(self.root['start'],self.root['size'])
  minis=[]; first=u32(data,60)
  for _ in range(u32(data,64)):
   minis.append(self.sector(first));first=u32(self.fat,first*4)
  self.minifat=b''.join(minis)
  self.entries={}
  def siblings(idx,parent,visited):
   if idx in (FREE,EOC) or idx>=len(self.items) or idx in visited: return
   visited.add(idx); item=self.items[idx]
   siblings(item['left'],parent,visited)
   path=parent+'/'+item['name'] if parent else item['name']; self.entries[path]=item
   if item['type']==1: siblings(item['child'],path,visited)
   siblings(item['right'],parent,visited)
  siblings(self.root['child'],'',set())
 def sector(self,id):
  i=512+id*self.secsize;return self.b[i:i+self.secsize]
 def chain(self,start,size=None,mini=False):
  b=b''; seen=set(); table=self.minifat if mini else self.fat; block=self.minisize if mini else self.secsize
  while start not in (FREE,EOC) and start not in seen and start*4+4<=len(table):
   seen.add(start)
   b+=self.ministream[start*block:(start+1)*block] if mini else self.sector(start)
   if size is not None and len(b)>=size:break
   start=u32(table,start*4)
  return b[:size] if size is not None else b
 def read(self,path):
  e=self.entries[path]
  return self.chain(e['start'], e['size'],e['size']<self.cutoff)

def sections(data):
 ole=Compound(data)
 try: compressed=bool(u32(ole.read('FileHeader'),36)&1)
 except Exception:compressed=True
 out=[]
 for name in sorted([k for k in ole.entries if re.fullmatch(r'BodyText/Section\d+',k)],key=lambda s:int(s.split('Section')[-1])):
  d=ole.read(name)
  if compressed:
   try:d=zlib.decompress(d,-15)
   except zlib.error:
    try:d=zlib.decompress(d)
    except zlib.error:continue
  off=0
  while off+4<=len(d):
   info=u32(d,off);off+=4
   tag=info&1023;sz=(info>>20)&4095
   if sz==4095:
    if off+4>len(d):break
    sz=u32(d,off);off+=4
   if off+sz>len(d):break
   payload=d[off:off+sz];off+=sz
   if tag==67:
    t=payload.decode('utf-16le','replace')
    t=re.sub('[\x00-\x08\x0b-\x1f]', ' ',t)
    t=' '.join(t.split())
    if t:out.append(t)
 return out
if __name__=='__main__':
 from pathlib import Path
 import sys
 p=Path(sys.argv[1]); rows=sections(p.read_bytes());print('paragraphs:',len(rows));print('\n'.join(rows[:170]))
