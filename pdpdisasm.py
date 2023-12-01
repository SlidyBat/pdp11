from binaryninja import *
from .pdpopcodes import *
from struct import unpack

def read_word(data):
    return unpack('<H', data[:2])[0]

def pdp11_decode(instr_data, addr):
    word, = unpack('<H', instr_data[:2])
    for op in pdp11_ops:
        mnem, bits, group = op
        if bits == (word >> group.shift):
            args = group.parse_args(instr_data)
            return mnem, args
    return None

def pdp11_disasm(instr_data, addr):
    op = pdp11_decode(instr_data, addr)
    if op == None:
        print('Unknown op', bin(read_word(instr_data)), '@', hex(addr))
        return None
    mnem, args = op
    result = [InstructionTextToken(InstructionTextTokenType.OpcodeToken, mnem)]
    length = 2
    for arg in args:
        length += 2 if arg.has_imm() else 0
    pc = addr + length
    if len(args) > 0:
        result.append(InstructionTextToken(InstructionTextTokenType.TextToken, ' '))
        if len(args) == 1:
            result += args[0].render(pc)
        elif len(args) == 2:
            result += args[0].render(pc)
            result.append(InstructionTextToken(InstructionTextTokenType.OperandSeparatorToken, ','))
            result.append(InstructionTextToken(InstructionTextTokenType.TextToken, ' '))
            result += args[1].render(pc)

    return result, length
