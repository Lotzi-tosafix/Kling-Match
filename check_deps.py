import struct, os

def get_dll_imports(path):
    with open(path, 'rb') as f:
        data = f.read()
    # Find MZ header
    if data[:2] != b'MZ':
        return []
    pe_offset = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe_offset:pe_offset+4] != b'PE\x00\x00':
        return []
    machine = struct.unpack_from('<H', data, pe_offset+4)[0]
    is64 = machine == 0x8664
    opt_offset = pe_offset + 24
    if is64:
        import_rva = struct.unpack_from('<I', data, opt_offset + 104)[0]
    else:
        import_rva = struct.unpack_from('<I', data, opt_offset + 104)[0]
    # Find section that contains import_rva
    num_sections = struct.unpack_from('<H', data, pe_offset+6)[0]
    sections_offset = opt_offset + (240 if is64 else 224)
    dlls = []
    for i in range(num_sections):
        s = sections_offset + i*40
        vaddr = struct.unpack_from('<I', data, s+12)[0]
        vsize = struct.unpack_from('<I', data, s+16)[0]
        raw   = struct.unpack_from('<I', data, s+20)[0]
        if vaddr <= import_rva < vaddr+vsize:
            off = raw + (import_rva - vaddr)
            while True:
                name_rva = struct.unpack_from('<I', data, off+12)[0]
                if name_rva == 0:
                    break
                name_off = raw + (name_rva - vaddr)
                end = data.index(b'\x00', name_off)
                dlls.append(data[name_off:end].decode())
                off += 20
    return dlls

dll = r"C:\Users\user\AppData\Local\Programs\Python\Python312\Lib\site-packages\torch\lib\fbgemm.dll"
deps = get_dll_imports(dll)
print("fbgemm.dll depends on:")
for d in deps:
    exists = "EXISTS" if any(
        os.path.exists(os.path.join(p, d))
        for p in os.environ.get('PATH','').split(';')
        if p
    ) else "MISSING"
    print(f"  {exists}: {d}")
