from binaryninja import *
from struct import unpack

REGISTERS = [
    'R0', 'R1', 'R2', 'R3', 'R4', 'R5', 'SP', 'PC'
]

USE_OCTAL = True

def sign_extend(value, bits):
    sign_bit = (1 << (bits - 1))
    return (value & (sign_bit - 1)) - (value & sign_bit)


class OpGroup:
    def __init__(self, shift, args):
        self.shift = shift
        self.args = args
    
    def parse_args(self, data):
        if len(data) < 6:
            data = data + b'\x00\x00\x00\x00'
        parsed = []
        instr, = unpack('<H', data[:2])
        imm_idx = 0
        imm, = unpack('<H', data[2:4])
        if len(self.args) > 1:
            parsed.append(self.args[1]())
            parsed[0].parse(instr, imm, 0)
            instr = instr >> parsed[-1].bit_width()
        if len(self.args) > 0:
            if len(parsed) > 0 and parsed[0].has_imm():
                imm, = unpack('<H', data[4:6])
                imm_idx = 1
            parsed.insert(0, self.args[0]())
            parsed[0].parse(instr, imm, 0)
        
        # Hack
        if len(self.args) == 2 and type(self.args[0]) == AddressedArg and type(self.args[1]) == AddressedArg:
            parsed[0], parsed[1] = parsed[1], parsed[0]

        return parsed

class AddressedArg:
    def parse(self, instr, imm, imm_idx):
        self.reg_idx = instr & 0b111
        self.mode = (instr >> 3) & 0b111
        self.imm = sign_extend(imm, 16)
        self.imm_idx = imm_idx

    def render(self, addr):
        if self.reg_idx == 7 and self.mode in [2, 3, 6, 7]:
            result = []
            if self.mode == 2:
                result.append(InstructionTextToken(InstructionTextTokenType.TextToken, '#'))
                result.append(InstructionTextToken(InstructionTextTokenType.IntegerToken, hex(self.imm), value=self.imm, size=2))
            elif self.mode == 3:
                result.append(InstructionTextToken(InstructionTextTokenType.TextToken, '@#'))
                result.append(InstructionTextToken(InstructionTextTokenType.IntegerToken, hex(self.imm), value=self.imm, size=2))
            elif self.mode == 6:
                result.append(InstructionTextToken(InstructionTextTokenType.CodeRelativeAddressToken, hex(self.imm), value=addr+self.imm, size=2))
            elif self.mode == 7:
                result.append(InstructionTextToken(InstructionTextTokenType.TextToken, '@'))
                result.append(InstructionTextToken(InstructionTextTokenType.IntegerToken, hex(self.imm), value=self.imm, size=2))
            return result
        
        prefix = []
        suffix = []
        if self.mode == 1:
            prefix.append(InstructionTextToken(InstructionTextTokenType.BeginMemoryOperandToken, '('))
            suffix.append(InstructionTextToken(InstructionTextTokenType.EndMemoryOperandToken, ')'))
        elif self.mode == 2:
            prefix.append(InstructionTextToken(InstructionTextTokenType.BeginMemoryOperandToken, '('))
            suffix.append(InstructionTextToken(InstructionTextTokenType.EndMemoryOperandToken, ')+'))
        if self.mode == 3:
            prefix.append(InstructionTextToken(InstructionTextTokenType.BeginMemoryOperandToken, '@('))
            suffix.append(InstructionTextToken(InstructionTextTokenType.EndMemoryOperandToken, ')+'))
        if self.mode == 4:
            prefix.append(InstructionTextToken(InstructionTextTokenType.BeginMemoryOperandToken, '-('))
            suffix.append(InstructionTextToken(InstructionTextTokenType.EndMemoryOperandToken, ')'))
        if self.mode == 5:
            prefix.append(InstructionTextToken(InstructionTextTokenType.BeginMemoryOperandToken, '@-('))
            suffix.append(InstructionTextToken(InstructionTextTokenType.EndMemoryOperandToken, ')'))
        if self.mode == 6:
            prefix.append(InstructionTextToken(InstructionTextTokenType.IntegerToken, oct(self.imm)[2:], value=self.imm, size=2))
            prefix.append(InstructionTextToken(InstructionTextTokenType.BeginMemoryOperandToken, '('))
            suffix.append(InstructionTextToken(InstructionTextTokenType.EndMemoryOperandToken, ')'))
        if self.mode == 7:
            prefix.append(InstructionTextToken(InstructionTextTokenType.TextToken, '@'))
            prefix.append(InstructionTextToken(InstructionTextTokenType.IntegerToken, oct(self.imm)[2:], value=self.imm, size=2))
            prefix.append(InstructionTextToken(InstructionTextTokenType.BeginMemoryOperandToken, '('))
            suffix.append(InstructionTextToken(InstructionTextTokenType.EndMemoryOperandToken, ')'))
        return prefix + [InstructionTextToken(InstructionTextTokenType.RegisterToken, REGISTERS[self.reg_idx])] + suffix

    def has_imm(self):
        if (self.reg_idx == 7 and self.mode in [2, 3, 6, 7]) or self.mode in [6, 7]:
            return True
        return False
    
    def get_value(self, addr, length):
        if self.reg_idx == 7:
            if self.mode == 2:
                return self.imm
            if self.mode == 3:
                return addr + (self.imm_idx + 1) * 2
            if self.mode == 6:
                return addr + length + self.imm
            if self.mode == 7:
                return None # ?
        return None
    
    def bit_width(self):
        return 6

class RegArg:
    def parse(self, instr, imm, imm_idx):
        self.reg_idx = instr & 0b111
    
    def render(self, addr):
        return [InstructionTextToken(InstructionTextTokenType.RegisterToken, REGISTERS[self.reg_idx])]

    def has_imm(self):
        return False
    
    def bit_width(self):
        return 3

class Const8Arg:
    def parse(self, instr, imm, imm_idx):
        self.value = sign_extend(instr & 0b11111111, 8)
    
    def render(self, addr):
        return [InstructionTextToken(InstructionTextTokenType.CodeRelativeAddressToken, hex(self.value), value=addr+2*self.value, size=2)]

    def has_imm(self):
        return False

    def bit_width(self):
        return 8

class Const6Arg:
    def parse(self, instr, imm, imm_idx):
        self.value = instr & 0b111111
    
    def render(self, addr):
        return [InstructionTextToken(InstructionTextTokenType.CodeRelativeAddressToken, hex(self.value), value=addr-2*self.value, size=2)]

    def has_imm(self):
        return False

    def bit_width(self):
        return 6

class Const4Arg:
    def parse(self, instr, imm, imm_idx):
        self.value = instr & 0b1111
    
    def render(self, addr):
        return [InstructionTextToken(InstructionTextTokenType.IntegerToken, hex(self.value), value=self.value, size=2)]

    def has_imm(self):
        return False

    def bit_width(self):
        return 4

DOUBLE_ADDRESSED_GROUP = OpGroup(shift=12, args=[AddressedArg, AddressedArg]) # Two addressed operands
ADDRESSED_REG_GROUP = OpGroup(shift=9, args=[RegArg, AddressedArg]) # One register operand, one addressed operand
ADDRESSED_GROUP = OpGroup(shift=6, args=[AddressedArg]) # One addressed operand
BRANCH_GROUP = OpGroup(shift=8, args=[Const8Arg]) # Branch instructions
SOB_GROUP = OpGroup(shift=9, args=[RegArg, Const6Arg]) # SOB instruction
RTS_GROUP = OpGroup(shift=3, args=[RegArg]) # RTS instruction
MARK_GROUP = OpGroup(shift=6, args=[Const6Arg]) # MARK instruction
NO_OPERAND_GROUP = OpGroup(shift=0, args=[]) # No operands
CONDITION_CODE_GROUP = OpGroup(shift=4, args=[Const4Arg]) # CCC/SCC instructions

pdp11_ops = [
    ('MOV', 0o01, DOUBLE_ADDRESSED_GROUP),
    ('MOVB', 0o11, DOUBLE_ADDRESSED_GROUP),
    ('CMP', 0o02, DOUBLE_ADDRESSED_GROUP),
    ('CMPB', 0o12, DOUBLE_ADDRESSED_GROUP),
    ('BIT', 0o03, DOUBLE_ADDRESSED_GROUP),
    ('BITB', 0o13, DOUBLE_ADDRESSED_GROUP),
    ('BIC', 0o04, DOUBLE_ADDRESSED_GROUP),
    ('BICB', 0o14, DOUBLE_ADDRESSED_GROUP),
    ('BIS', 0o05, DOUBLE_ADDRESSED_GROUP),
    ('BISB', 0o15, DOUBLE_ADDRESSED_GROUP),
    ('ADD', 0o06, DOUBLE_ADDRESSED_GROUP),
    ('SUB', 0o16, DOUBLE_ADDRESSED_GROUP),

    ('JSR', 0o004, ADDRESSED_REG_GROUP),
    ('MUL', 0o070, ADDRESSED_REG_GROUP),
    ('DIV', 0o071, ADDRESSED_REG_GROUP),
    ('ASH', 0o072, ADDRESSED_REG_GROUP),
    ('ASHC', 0o073, ADDRESSED_REG_GROUP),
    ('XOR', 0o074, ADDRESSED_REG_GROUP),

    ('JMP', 0o0001, ADDRESSED_GROUP),
    ('SWAB', 0o0003, ADDRESSED_GROUP),
    ('CLR', 0o0050, ADDRESSED_GROUP),
    ('CLRB', 0o1050, ADDRESSED_GROUP),
    ('COM', 0o0051, ADDRESSED_GROUP),
    ('COMB', 0o1051, ADDRESSED_GROUP),
    ('INC', 0o0052, ADDRESSED_GROUP),
    ('INCB', 0o1052, ADDRESSED_GROUP),
    ('DEC', 0o0053, ADDRESSED_GROUP),
    ('DECB', 0o1053, ADDRESSED_GROUP),
    ('NEG', 0o0054, ADDRESSED_GROUP),
    ('NEGB', 0o1054, ADDRESSED_GROUP),
    ('ADC', 0o0055, ADDRESSED_GROUP),
    ('ADCB', 0o1055, ADDRESSED_GROUP),
    ('SBC', 0o0056, ADDRESSED_GROUP),
    ('SBCB', 0o1056, ADDRESSED_GROUP),
    ('TST', 0o0057, ADDRESSED_GROUP),
    ('TSTB', 0o1057, ADDRESSED_GROUP),
    ('ROR', 0o0060, ADDRESSED_GROUP),
    ('RORB', 0o1060, ADDRESSED_GROUP),
    ('ROL', 0o0061, ADDRESSED_GROUP),
    ('ROLB', 0o1061, ADDRESSED_GROUP),
    ('ASR', 0o0062, ADDRESSED_GROUP),
    ('ASRB', 0o1062, ADDRESSED_GROUP),
    ('ASL', 0o0063, ADDRESSED_GROUP),
    ('ASLB', 0o1063, ADDRESSED_GROUP),
    ('MTPS', 0o1064, ADDRESSED_GROUP),
    ('MFPI', 0o0065, ADDRESSED_GROUP),
    ('MFPD', 0o1065, ADDRESSED_GROUP),
    ('MTPI', 0o0066, ADDRESSED_GROUP),
    ('MTPD', 0o1066, ADDRESSED_GROUP),
    ('SXT', 0o0067, ADDRESSED_GROUP),
    ('MFPS', 0o1067, ADDRESSED_GROUP),

    ('BR', (0o000 << 1) | 1, BRANCH_GROUP),
    ('BNE', (0o001 << 1) | 0, BRANCH_GROUP),
    ('BEQ', (0o001 << 1) | 1, BRANCH_GROUP),
    ('BGE', (0o002 << 1) | 0, BRANCH_GROUP),
    ('BLT', (0o002 << 1) | 1, BRANCH_GROUP),
    ('BGT', (0o003 << 1) | 0, BRANCH_GROUP),
    ('BLE', (0o003 << 1) | 1, BRANCH_GROUP),
    ('BPL', (0o100 << 1) | 0, BRANCH_GROUP),
    ('BMI', (0o100 << 1) | 1, BRANCH_GROUP),
    ('BHI', (0o101 << 1) | 0, BRANCH_GROUP),
    ('BLOS', (0o101 << 1) | 1, BRANCH_GROUP),
    ('BVC', (0o102 << 1) | 0, BRANCH_GROUP),
    ('BVS', (0o102 << 1) | 1, BRANCH_GROUP),
    ('BCC', (0o103 << 1) | 0, BRANCH_GROUP),
    ('BCS', (0o103 << 1) | 1, BRANCH_GROUP),
    ('EMT', (0o104 << 1) | 0, BRANCH_GROUP),
    ('TRAP', (0o104 << 1) | 1, BRANCH_GROUP),

    ('SOB', 0o077, SOB_GROUP),

    ('RTS', 0o00020, RTS_GROUP),

    ('MARK', 0o0064, MARK_GROUP),

    ('HALT', 0o000000, NO_OPERAND_GROUP),
    ('WAIT', 0o000001, NO_OPERAND_GROUP),
    ('RTI', 0o000002, NO_OPERAND_GROUP),
    ('BPT', 0o000003, NO_OPERAND_GROUP),
    ('IOT', 0o000004, NO_OPERAND_GROUP),
    ('RESET', 0o000005, NO_OPERAND_GROUP),
    ('RTT', 0o000006, NO_OPERAND_GROUP),

    ('CCC', 0o00012, CONDITION_CODE_GROUP),
    ('SCC', 0o00013, CONDITION_CODE_GROUP),
]