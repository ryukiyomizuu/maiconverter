using System.Text.Encodings.Web;
using System.Text.Json;
using MaiConverter.Custom.Core.Models;

namespace MaiConverter.Custom.Core.Services;

public static class CollectionManifestWriter
{
    private sealed class TrackGroup
    {
        public string? name { get; set; }
        public string[]? levelIds { get; set; }
    }

    public static void WriteCollections(DirectoryInfo outputRoot, IReadOnlyCollection<TrackMetadata> tracks)
    {
        if (!outputRoot.Exists)
        {
            outputRoot.Create();
        }

        var options = new JsonSerializerOptions
        {
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            WriteIndented = true,
        };

        var versions = tracks.Select(t => t.TrackVersion).Distinct().ToArray();
        var genres = tracks.Select(t => t.TrackGenre).Distinct().ToArray();
        var prefixes = tracks.Select(t => t.StandardDeluxePrefix).Distinct().ToArray();

        var groups = new List<TrackGroup>();
        groups.AddRange(versions.Select(version => new TrackGroup
        {
            name = version,
            levelIds = tracks.Where(t => t.TrackVersion == version).Select(t => t.TrackId).ToArray(),
        }));
        groups.AddRange(genres.Select(genre => new TrackGroup
        {
            name = genre == "maimai" ? "Original" : genre,
            levelIds = tracks.Where(t => t.TrackGenre == genre).Select(t => t.TrackId).ToArray(),
        }));
        groups.AddRange(prefixes.Select(prefix => new TrackGroup
        {
            name = $"{prefix} Chart",
            levelIds = tracks.Where(t => t.StandardDeluxePrefix == prefix).Select(t => t.TrackId).ToArray(),
        }));

        foreach (var group in groups)
        {
            if (string.IsNullOrWhiteSpace(group.name))
            {
                continue;
            }

            var safeName = SanitizeFileName(group.name);
            var manifestPath = Path.Combine(outputRoot.FullName, $"{safeName}.json");
            var json = JsonSerializer.Serialize(group, options);
            File.WriteAllText(manifestPath, json);
        }
    }

    private static string SanitizeFileName(string name)
    {
        var invalid = Path.GetInvalidFileNameChars();
        var cleaned = new string(name.Select(ch => invalid.Contains(ch) ? '_' : ch).ToArray());
        return cleaned.Trim();
    }
}
