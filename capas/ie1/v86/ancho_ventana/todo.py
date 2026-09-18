import desens, capstone
g = desens.g
md = g['md']; md.skipdata = True
data = g['data']
with open('todo.txt','w') as f:
    for ins in md.disasm(data[0x180:0x180+0x197d1c], 0x180):
        f.write(f'{ins.address:6x}  {ins.mnemonic:8s} {ins.op_str}\n')
