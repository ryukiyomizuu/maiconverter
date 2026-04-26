using System.Text.Encodings.Web;
using System.Text.Json;

namespace MaiConverter.Custom.Core.Services;

public static class LogWriter
{
    public static void WriteTextLog(DirectoryInfo outputDir, IReadOnlyDictionary<int, string> compiledTracks, IReadOnlyList<string> warnings)
    {
        if (!outputDir.Exists)
        {
            outputDir.Create();
        }

        var logPath = Path.Combine(outputDir.FullName, "forge.log");
        using var writer = new StreamWriter(logPath, false);
        var index = 1;
        foreach (var pair in compiledTracks.OrderBy(kv => kv.Key))
        {
            writer.WriteLine($"[{index}]: {pair.Key} {pair.Value}");
            index++;
        }

        if (warnings.Count > 0)
        {
            writer.WriteLine();
            writer.WriteLine("Warnings:");
            foreach (var warning in warnings)
            {
                writer.WriteLine(warning);
            }
        }
    }

    public static void WriteJsonIndex(DirectoryInfo outputDir, IReadOnlyDictionary<int, string> compiledTracks)
    {
        if (!outputDir.Exists)
        {
            outputDir.Create();
        }

        var jsonPath = Path.Combine(outputDir.FullName, "tracks.json");
        var options = new JsonSerializerOptions
        {
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            WriteIndented = true,
        };
        var sorted = new SortedDictionary<int, string>(compiledTracks.ToDictionary(kv => kv.Key, kv => kv.Value));
        var json = JsonSerializer.Serialize(sorted, options);
        File.WriteAllText(jsonPath, json);
    }
}
