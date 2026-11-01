// Validates a TMSL model with Microsoft's Tabular Object Model (TOM), writes the canonical TMSL back and a TMDL folder.
// Build: mcs tomcheck.cs -r:Microsoft.AnalysisServices.Tabular.dll -r:Microsoft.AnalysisServices.Core.dll -r:Microsoft.AnalysisServices.Tabular.Json.dll
// Run:   mono tomcheck.exe model.bim canonical.bim tmdl_folder
using System;
using System.IO;
using System.Linq;
using Microsoft.AnalysisServices.Tabular;

class TomCheck {
  static int Main(string[] a) {
    var db = JsonSerializer.DeserializeDatabase(File.ReadAllText(a[0]));   // throws on any structural or reference error
    var m = db.Model;
    Console.WriteLine("compatibility " + db.CompatibilityLevel + "; tables " + m.Tables.Count + "; measures " +
                      m.Tables.Sum(t => t.Measures.Count) + "; relationships " + m.Relationships.Count + "; expressions " + m.Expressions.Count);
    foreach (var t in m.Tables) {
      foreach (var c in t.Columns) if (c.SortByColumn != null) Console.WriteLine("sort-by  " + t.Name + "[" + c.Name + "] by " + c.SortByColumn.Name);
      if (t.DataCategory == "Time") Console.WriteLine("date table " + t.Name + " key " + string.Join(",", t.Columns.Where(c => c.IsKey).Select(c => c.Name)));
    }
    foreach (SingleColumnRelationship r in m.Relationships)
      Console.WriteLine("relation " + r.FromTable.Name + "[" + r.FromColumn.Name + "] -> " + r.ToTable.Name + "[" + r.ToColumn.Name + "] " +
                        r.FromCardinality + ":" + r.ToCardinality + " " + r.CrossFilteringBehavior + " active=" + r.IsActive);
    var opts = new SerializeOptions { IgnoreTimestamps = true, IgnoreInferredObjects = true, IgnoreInferredProperties = true };
    File.WriteAllText(a[1], JsonSerializer.SerializeDatabase(db, opts));
    if (Directory.Exists(a[2])) Directory.Delete(a[2], true);
    TmdlSerializer.SerializeDatabaseToFolder(db, a[2]);
    var back = TmdlSerializer.DeserializeDatabaseFromFolder(a[2]);           // round trip proves the TMDL is readable
    Console.WriteLine("TMDL round trip: tables " + back.Model.Tables.Count + ", measures " + back.Model.Tables.Sum(t => t.Measures.Count));
    return 0;
  }
}
