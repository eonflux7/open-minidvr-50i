// Adds the 16 code banks as CODE overlays at 0x8000 and seeds entry points.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import java.io.*;

public class SetupBanks extends GhidraScript {
    @Override
    public void run() throws Exception {
        String dir = getScriptArgs()[0];
        Memory mem = currentProgram.getMemory();
        AddressSpace code = currentProgram.getAddressFactory().getAddressSpace("CODE");
        for (int b = 1; b <= 16; b++) {
            File f = new File(dir, String.format("bank%02d.bin", b));
            try (InputStream in = new FileInputStream(f)) {
                MemoryBlock blk = mem.createInitializedBlock(String.format("bank%02d", b),
                    code.getAddress(0x8000), in, f.length(), monitor, true);
                blk.setExecute(true);
            }
        }
        // Keil runtime helpers manipulate the stack, which fools no-return discovery.
        setAnalysisOption(currentProgram, "Non-Returning Functions - Discovered", "false");
        disassemble(code.getAddress(0));
        createFunction(code.getAddress(0), "reset_vec");
        println("banks added");
    }
}
