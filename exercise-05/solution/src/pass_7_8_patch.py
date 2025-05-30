import ast_7_mem as src
import ast_8_patched as tgt
from register import *
from label import *
from util.immutable_list import ilist

def patch_instructions(p: src.Program) -> tgt.Program:
    out: tgt.Program = {}
    for label, block in p.items():
        block_out: tgt.Block = ilist()
        for i in block:
            block_out += patch_instruction(i)
        out[label] = block_out
    return out

def patch_instruction(i: src.Instr) -> tgt.Block:
    out: tgt.Block = ilist()
    match i:
        case src.Move(dst, src_):
            match dst:
                case src.Register(_):
                    rd = dst
                    dst_address = None
                case src.Offset(_, _):
                    rd = t0
                    dst_address = dst
            match src_:
                case src.Register(_):
                    out += ilist(tgt.RInstr("add", rd, zero, src_))
                case src.Offset(_, _):
                    out += patch_load_offset(rd, src_)
                case src.Const(c):
                    out += ilist(tgt.IInstr1("li", rd, patch_const(src_)))

            if dst_address is not None:
                out += patch_store_offset(t0, dst_address, t1)
        case src.Call(l):
            out += ilist(tgt.Call(l))
        case src.Jump(l):
            out += ilist(tgt.Jump(l))
        case src.Branch(cc, src1, src2, l):
            match src1:
                case Register(_):
                    rs1 = src1
                case src.Offset(_, _):
                    out += patch_load_offset(t0, src1)
                    rs1 = t0
                case src.Const(c):
                    out += ilist(tgt.IInstr1("li", t0, patch_const(src1)))
                    rs1 = t0
            match src2:
                case Register(_):
                    rs2 = src2
                case src.Offset(_, _):
                    out += patch_load_offset(t1, src2)
                    rs2 = t1
                case src.Const(c):
                    out += ilist(tgt.IInstr1("li", t1, patch_const(src2)))
                    rs2 = t1
            out += ilist(tgt.Branch(cc, rs1, rs2, l))
        case src.Instr2(op, dst, src1, src2):
            match dst:
                case Register(_):
                    rd = dst
                    dst_address = None
                case src.Offset(_, _):
                    rd = t0
                    dst_address = dst
            match src1:
                case src.Register(_):
                    rs1 = src1
                case src.Offset(_, _):
                    out += patch_load_offset(t0, src1)
                    rs1 = t0
                case src.Const(c):
                    out += ilist(tgt.IInstr1("li", t0, patch_const(src1)))
                    rs1 = t0
            match src2:
                case src.Register(_):
                    rs2 = src2
                case src.Offset(_, _):
                    out += patch_load_offset(t1, src2)
                    rs2 = t1
                case src.Const(_):
                    c = patch_const(src2)
                    # Use immediate if constant doesn't need many bits
                    if op not in ["sltu", "div", "mul"] and c < 2**11 and c > -(2**11):
                        rs2 = c # type: ignore
                    # Otherwise load it into a register first, where
                    # the pseudo-instruction `li` will use, e.g. a
                    # combination of addi and shifts to load to
                    # constant piece by piece.
                    else:
                        out += ilist(tgt.IInstr1("li", t1, c))
                        rs2 = t1
            match rs2:
                case int(c):
                    match op:
                        case "add":
                            out += ilist(tgt.IInstr2("addi", rd, rs1, rs2))
                        case "sub":
                            out += ilist(tgt.IInstr2("addi", rd, rs1, -rs2))
                        case "xor":
                            out += ilist(tgt.IInstr2("xori", rd, rs1, rs2))
                        case "slt":
                            out += ilist(tgt.IInstr2("slti", rd, rs1, rs2))
                        case "sll":
                            out += ilist(tgt.IInstr2("slli", rd, rs1, rs2))
                        case "srl":
                            out += ilist(tgt.IInstr2("srli", rd, rs1, rs2))
                        case "sltu":
                            out += ilist(tgt.IInstr2("sltiu", rd, rs1, rs2)) 
                case Register(_):
                    out += ilist(tgt.RInstr(op, rd, rs1, rs2))

            if dst_address is not None:
                out += patch_store_offset(t0, dst_address, t1)
    return out

def patch_const(e: src.Const) -> tgt.Const:
    match e.size:
        case "63bit":
            return int(e.value) << 1
        case "64bit":
            return int(e.value)

def patch_load_offset(rd: Register, o: src.Offset) -> tgt.Block:
    match o.reg:
        case Register(_):
            return ilist(
                tgt.Load(rd, tgt.Offset(o.reg, o.offset))
            )
        case Label(_) as l:
            return ilist(
                tgt.LoadAddress(rd, l),
                tgt.Load(rd, tgt.Offset(rd, o.offset)),
            )
        case src.Offset(_):
            out = patch_load_offset(rd, o.reg)
            out += ilist(
                tgt.Load(rd, tgt.Offset(rd, o.offset))
            )
            return out

def patch_store_offset(rs: Register, o: src.Offset, rtmp: Register) -> tgt.Block:
    match o.reg:
        case Register(_):
            return ilist(
                tgt.Store(rs, tgt.Offset(o.reg, o.offset))
            )
        case Label(_) as l:
            return ilist(
                tgt.LoadAddress(rtmp, l),
                tgt.Store(rs, tgt.Offset(rtmp, o.offset)),
            )
        case src.Offset(_):
            out = patch_load_offset(rtmp, o.reg)
            out += ilist(
                tgt.Store(rs, tgt.Offset(rtmp, o.offset))
            )
            return out
