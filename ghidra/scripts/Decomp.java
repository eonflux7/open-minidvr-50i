// Decompiles the functions containing each "space:hexaddr" argument; last arg is output file.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class Decomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(new FileWriter(args[args.length - 1]))) {
            for (int i = 0; i < args.length - 1; i++) {
                Address a = currentProgram.getAddressFactory().getAddress(args[i]);
                Function f = getFunctionContaining(a);
                if (f == null) { disassemble(a); f = createFunction(a, null); }
                if (f == null) { out.println("// no function at " + args[i]); continue; }
                DecompileResults r = di.decompileFunction(f, 120, monitor);
                out.println("// ===== " + f.getEntryPoint() + " " + f.getName());
                out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// failed: " + r.getErrorMessage());
            }
        }
    }
}
