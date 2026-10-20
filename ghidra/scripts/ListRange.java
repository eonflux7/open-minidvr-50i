// Prints the listing (address, bytes, instruction or data) for "space:start" "space:end" pairs; last arg is output file.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class ListRange extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        AddressFactory af = currentProgram.getAddressFactory();
        try (PrintWriter out = new PrintWriter(new FileWriter(a[a.length - 1]))) {
            for (int i = 0; i + 1 < a.length - 1; i += 2) {
                AddressSet set = new AddressSet(af.getAddress(a[i]), af.getAddress(a[i + 1]));
                out.println("; ---- " + a[i] + " .. " + a[i + 1]);
                for (CodeUnit cu : currentProgram.getListing().getCodeUnits(set, true)) {
                    Function f = getFunctionAt(cu.getAddress());
                    if (f != null) out.println(f.getName() + ":");
                    StringBuilder hex = new StringBuilder();
                    for (byte b : cu.getBytes()) hex.append(String.format("%02x", b & 0xff));
                    out.printf("  %s  %-12s %s%n", cu.getAddress(), hex, cu.toString());
                }
            }
        }
    }
}
