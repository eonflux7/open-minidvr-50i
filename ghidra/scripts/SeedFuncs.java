// Seeds functions from LCALL targets: common-area targets (0x0000-0x7FFF) anywhere,
// banked targets (0x8000+) within the calling bank's overlay.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import java.util.*;

public class SeedFuncs extends GhidraScript {
    @Override
    public void run() throws Exception {
        Memory mem = currentProgram.getMemory();
        int made = 0;
        for (MemoryBlock blk : mem.getBlocks()) {
            if (!blk.isInitialized() || !blk.getStart().getAddressSpace().getName().matches("CODE|bank\\d\\d")) continue;
            boolean overlay = blk.isOverlay();
            byte[] b = new byte[(int) blk.getSize()];
            blk.getBytes(blk.getStart(), b);
            Set<Integer> targets = new TreeSet<>();
            for (int i = 0; i + 2 < b.length; i++)
                if ((b[i] & 0xff) == 0x12) targets.add(((b[i + 1] & 0xff) << 8) | (b[i + 2] & 0xff));
            if (overlay) targets.add(0x8000);
            for (int t : targets) {
                Address a;
                if (t < 0x8000) {
                    if (overlay) continue; // common targets are seeded from the common block's own scan
                    a = blk.getStart().getAddressSpace().getAddress(t);
                } else {
                    if (!overlay) continue;
                    a = blk.getStart().getAddressSpace().getAddress(t);
                }
                if (!blk.contains(a) || getFunctionAt(a) != null) continue;
                if (getInstructionAt(a) == null && !disassemble(a)) continue;
                if (createFunction(a, null) != null) made++;
            }
        }
        println("functions seeded: " + made);
    }
}
