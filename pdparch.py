from binaryninja import *
from .pdpdisasm import *

class BSD2(Platform):
    name = '2.11bsd'

class PDP11(Architecture):
    name = 'pdp11'
    
    address_size = 2
    default_int_size = 2
    instr_alignment = 2
    max_instr_length = 6
    
    regs = {
        'r0': RegisterInfo('r0', 2),
        'r1': RegisterInfo('r1', 2),
        'r2': RegisterInfo('r2', 2),
        'r3': RegisterInfo('r3', 2),
        'r4': RegisterInfo('r4', 2),
        'r5': RegisterInfo('r5', 2),
        
        'sp': RegisterInfo('sp', 2),
    }
    
    stack_pointer = 'sp'
    
    def __init__(self):
        Architecture.__init__(self)
    
    def get_instruction_info(self, data, addr):
        op = pdp11_decode(data, addr)
        if op == None:
            return None
        
        mnem, args = op

        info = InstructionInfo()
        info.length = 2
        for arg in args:
            if arg.has_imm():
                info.length += 2
        if addr == 0:
            print('0',info.length)

        if mnem in ['RTS', 'MARK', 'HALT']:
            info.add_branch(BranchType.FunctionReturn)
        elif mnem in ['JSR']:
            target = args[1].get_value(addr, info.length)
            if target is None:
                info.add_branch(BranchType.IndirectBranch)
            else:
                info.add_branch(BranchType.CallDestination, target)
        elif mnem in ['JMP']:
            target = args[0].get_value(addr, info.length)
            if target is None:
                info.add_branch(BranchType.IndirectBranch)
            else:
                info.add_branch(BranchType.UnconditionalBranch, target)
        elif mnem in ['BR']:
            target = args[0].value
            info.add_branch(BranchType.UnconditionalBranch, addr + info.length + target*2)
        elif mnem in ['BNE', 'BEQ', 'BGE', 'BLT', 'BGT', 'BLE', 'BPL', 'BMI', 'BHI', 'BLOS', 'BVC', 'BVS', 'BCC', 'BCS']:
            target = args[0].value
            info.add_branch(BranchType.TrueBranch, addr + info.length + target*2)
            info.add_branch(BranchType.FalseBranch, addr + info.length)
        elif mnem in ['SOB']:
            target = args[1].value
            info.add_branch(BranchType.TrueBranch, addr + info.length - target*2)
            info.add_branch(BranchType.FalseBranch, addr + info.length)
        elif mnem in ['MOV'] and args[1].reg_idx == 7:
            info.add_branch(BranchType.FunctionReturn)

        return info
    
    def get_instruction_text(self, data, addr):
        disasm = pdp11_disasm(data, addr)
        if disasm == None:
            return None
        return disasm
    
    def get_instruction_low_level_il(self, data, addr, il):
        return None