"""Make an upside-down copy (rotate 180 deg about X, then lift back to y>=0) of a .glb whose mesh nodes carry no transforms."""
import struct,json,numpy as np,sys
def flip(src,dst):
    b=bytearray(open(src,'rb').read()); jl=struct.unpack('<I',b[12:16])[0]; j=json.loads(bytes(b[20:20+jl])); off=20+jl+8
    prims=[p for m in j['meshes'] for p in m['primitives']]
    pa=sorted({p['attributes']['POSITION'] for p in prims})
    # global top y so the whole mesh keeps y in [0, H]
    H=max(max(j['accessors'][a]['max'][1] for a in pa),0)
    done=set()
    def view(ai,n):
        a=j['accessors'][ai]; bv=j['bufferViews'][a['bufferView']]
        assert a['componentType']==5126 and 'sparse' not in a
        stride=bv.get('byteStride',0)
        assert stride in (0,n*4),stride
        s=off+bv.get('byteOffset',0)+a.get('byteOffset',0)
        return np.frombuffer(b,'<f4',a['count']*n,s).reshape(-1,n)
    for p in prims:
        for key,n in(('POSITION',3),('NORMAL',3),('TANGENT',4)):
            ai=p['attributes'].get(key)
            if ai is None or (key,ai) in done: continue
            done.add((key,ai)); v=view(ai,n)
            if key=='POSITION':
                v[:,1]=H-v[:,1]; v[:,2]=-v[:,2]
                a=j['accessors'][ai]; a['min']=[float(x) for x in v.min(0)]; a['max']=[float(x) for x in v.max(0)]
            else:
                v[:,1]=-v[:,1]; v[:,2]=-v[:,2]
    open(dst,'wb').write(bytes(b))
    return H
if __name__=="__main__":
    print(flip(sys.argv[1],sys.argv[2]))
