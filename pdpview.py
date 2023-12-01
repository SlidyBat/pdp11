from binaryninja import *
from .typebuilder import *
from struct import unpack
import zlib

class PDP11View(BinaryView):
    name = 'PDP-11'
    long_name = 'PDP-11 Executable'

    @classmethod
    def is_valid_for_data(self, data):
        # There are bunch of possible magic numbers, but I'm just doing this for Flare-On, so only checking normal one
        # See: https://github.com/RetroBSD/2.11BSD/blob/master/usr/sys/h/exec.h#L39-L44
        magic = data.read(0, 2)
        return magic == b'\x07\x01'
    
    def __init__(self, data):
        BinaryView.__init__(self, parent_view=data, file_metadata=data.file)
        
        self.data = data
        self.arch = Architecture['pdp11']
        self.platform = Platform['2.11bsd']
    
    def perform_is_executable(self):
        return True
    
    def perform_get_address_size(self):
        return 2
    
    def perform_get_entry_point(self):
        return 0x20
    
    def init(self):
        # See: https://github.com/RetroBSD/2.11BSD/blob/master/usr/sys/h/exec.h#L14C1-L23C3
        self.a_text, = unpack('<H', self.data.read(2, 2))
        self.a_data, = unpack('<H', self.data.read(4, 2))
        self.a_bss, = unpack('<H', self.data.read(6, 2))
        self.a_syms, = unpack('<H', self.data.read(8, 2))
        self.a_entry, = unpack('<H', self.data.read(10, 2))
        self.a_flag, = unpack('<H', self.data.read(14, 2))

        log_info('a_text=%x' % self.a_text)
        log_info('a_data=%x' % self.a_data)
        log_info('a_bss=%x' % self.a_bss)
        log_info('a_syms=%x' % self.a_syms)
        log_info('a_entry=%x' % self.a_entry)
        log_info('a_flag=%x' % self.a_flag)
        log_info('txtoff=%x' % self.txtoff())
        log_info('symoff=%x' % self.symoff())
        log_info('stroff=%x' % self.stroff())
        
        strsiz, = unpack('<H', self.data.read(self.stroff() + 2, 2))

        hdrsiz = 0x10

        self.add_auto_segment(self.txtoff() - hdrsiz, self.a_text, self.txtoff(), self.a_text, SegmentFlag.SegmentContainsCode|SegmentFlag.SegmentReadable|SegmentFlag.SegmentExecutable)
        self.add_auto_segment(self.dataoff() - hdrsiz, self.a_data, self.dataoff(), self.a_data, SegmentFlag.SegmentContainsData|SegmentFlag.SegmentReadable|SegmentFlag.SegmentWritable)
        self.add_auto_segment(self.symoff() - hdrsiz, self.a_syms, self.symoff(), self.a_syms, SegmentFlag.SegmentContainsData|SegmentFlag.SegmentReadable)
        self.add_auto_segment(self.stroff() - hdrsiz, strsiz, self.stroff(), strsiz, SegmentFlag.SegmentContainsData|SegmentFlag.SegmentReadable)

        self.add_auto_section('.text', self.txtoff() - hdrsiz, self.a_text, SectionSemantics.ReadOnlyCodeSectionSemantics)
        self.add_auto_section('.data', self.dataoff() - hdrsiz, self.a_data, SectionSemantics.ReadWriteDataSectionSemantics)
        self.add_auto_section('.syms', self.symoff() - hdrsiz, self.a_syms, SectionSemantics.ReadOnlyDataSectionSemantics)
        self.add_auto_section('.strtab', self.stroff() - hdrsiz, strsiz, SectionSemantics.ReadOnlyDataSectionSemantics)

        nsyms = self.a_syms // 8
        syms = []
        br = self.data.reader(self.symoff())
        for _ in range(nsyms):
            pad = br.read16()
            n_strx = br.read16()
            n_name = self.read_cstr(self.stroff() + n_strx)
            n_type = br.read8()
            n_ovly = br.read8()
            n_value = br.read16()
            #log_info('n_name=%s, n_type=%i, n_value=%i' % (n_name, n_type, n_value))
            syms.append((n_name, n_type, n_ovly, n_value))
        
        self.define_symbols(syms)

        return True

    def txtoff(self):
        # See: https://github.com/RetroBSD/2.11BSD/blob/master/usr/include/a.out.h#L46-L48
        return 0x10 # sizeof(exec)

    def symoff(self):
        # See: https://github.com/RetroBSD/2.11BSD/blob/master/usr/lib/libc/pdp/gen/nsym.c#L79
        l = self.txtoff()
        sum = self.a_text + self.a_data
        l += sum
        if (self.a_flag & 1) == 0:
            l += sum
        return l

    def stroff(self):
        return self.symoff() + self.a_syms
    
    def dataoff(self):
        return 0x10 + self.a_text
    
    def read_cstr(self, addr):
        s = ''
        while True:
            c = self.data.read(addr, 1)
            if c[0] == 0:
                break
            s += c.decode()
            addr += 1
        return s
    
    def define_symbols(self, syms):
        for sym in syms:
            n_name, n_type, _, n_value = sym

            # See: https://github.com/RetroBSD/2.11BSD/blob/master/usr/include/nlist.h#L66-L78
            # n_ext = n_type & 0x20
            n_type = n_type & 0x1f
            if n_type == 0x2: # t/T
                # Hack for flare-on
                if n_name.endswith('_xt'):
                    continue
                self.add_function(n_value)
                self.define_auto_symbol(Symbol(SymbolType.FunctionSymbol, n_value, n_name))
            elif n_type == 0x3: # d/D
                # Don't know data type, so just assume int16_t, since binja doesn't allow labelling untyped addresses
                self.define_data_var(n_value, 'int16_t', n_name)