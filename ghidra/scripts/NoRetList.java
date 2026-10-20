// Lists functions marked non-returning, with call counts and their first bytes.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class NoRetList extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (!f.hasNoReturn()) continue;
            int n = 0;
            for (Reference r : getReferencesTo(f.getEntryPoint())) if (r.getReferenceType().isCall()) n++;
            byte[] b = getBytes(f.getEntryPoint(), 24);
            StringBuilder s = new StringBuilder();
            for (byte x : b) s.append(String.format("%02x", x & 0xff));
            println(String.format("NORET %s calls=%d %s", f.getEntryPoint(), n, s));
        }
    }
}
