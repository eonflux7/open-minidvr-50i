// For each "space:addr" target: lists call sites and decompiles each calling function. Last arg is output file.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class Callers extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        Set<Function> done = new HashSet<>();
        try (PrintWriter out = new PrintWriter(new FileWriter(a[a.length - 1]))) {
            for (int i = 0; i < a.length - 1; i++) {
                Address t = currentProgram.getAddressFactory().getAddress(a[i]);
                out.println("// #### callers of " + t);
                for (Reference r : getReferencesTo(t)) {
                    out.println("//   " + r.getFromAddress() + " " + r.getReferenceType());
                    Function f = getFunctionContaining(r.getFromAddress());
                    if (f == null || !done.add(f)) continue;
                    DecompileResults res = di.decompileFunction(f, 120, monitor);
                    out.println("// ===== " + f.getEntryPoint());
                    out.println(res.decompileCompleted() ? res.getDecompiledFunction().getC() : "// failed");
                }
            }
        }
    }
}
