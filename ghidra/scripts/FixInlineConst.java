// Keil C51 helpers that take an inline 4-byte constant after the LCALL (e.g. ?C?LSTKXDATA):
// mark them returning, make the 4 bytes data, and set each call's fallthrough past them.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.data.DWordDataType;

public class FixInlineConst extends GhidraScript {
    @Override
    public void run() throws Exception {
        int[] helpers = {0x3b1a};
        AddressSpace code = currentProgram.getAddressFactory().getAddressSpace("CODE");
        for (int h : helpers) {
            Function hf = getFunctionAt(code.getAddress(h));
            if (hf != null) hf.setNoReturn(false);
        }
        Memory mem = currentProgram.getMemory();
        int total = 0, fixed;
        do {
        fixed = 0;
        for (MemoryBlock blk : mem.getBlocks()) {
            if (!blk.isInitialized() || !blk.isExecute()) continue;
            byte[] b = new byte[(int) blk.getSize()];
            blk.getBytes(blk.getStart(), b);
            for (int i = 0; i + 7 <= b.length; i++) {
                if ((b[i] & 0xff) != 0x12) continue;
                int t = ((b[i + 1] & 0xff) << 8) | (b[i + 2] & 0xff);
                boolean match = false;
                for (int h : helpers) match |= (t == h);
                if (!match) continue;
                Address call = blk.getStart().add(i);
                Instruction ins = getInstructionAt(call);
                if (ins == null) continue; // only fix real, already-disassembled calls
                if (ins.getFallThrough() != null && ins.getFallThrough().equals(call.add(7))) continue;
                Address dat = call.add(3);
                clearListing(dat, dat.add(3));
                createData(dat, new DWordDataType());
                ins.setFallThrough(call.add(7));
                disassemble(call.add(7));
                fixed++;
            }
        }
        total += fixed;
        } while (fixed > 0);
        println("inline-const calls fixed: " + total);
    }
}
