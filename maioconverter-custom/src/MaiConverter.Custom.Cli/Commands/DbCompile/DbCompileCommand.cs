using MaiConverter.Custom.Cli.Parsing;
using MaiConverter.Custom.Core.Enums;
using MaiConverter.Custom.Core.Models;
using MaiConverter.Custom.Core.Services;
using MaiLib;

namespace MaiConverter.Custom.Cli.Commands.DbCompile;

public sealed class DbCompileCommand : ICommand
{
    public string Name => "db-compile";
    public IReadOnlyList<string> Aliases => ["CompileDatabase"];
    public string Description => "Compile an AXXX database into Simai output folders.";

    public int Run(string[] args)
    {
        try
        {
            var parsed = OptionParser.Parse(args, GetOptionSpecs());
            var input = RequireValue(parsed, "input");
            var output = RequireValue(parsed, "output");
            var resolvedOutput = OutputPathHelper.Resolve(output, input) ?? output;
            var categoryIndex = RequireInt(parsed, "category");

            var detection = AxxxDetector.Detect(new DirectoryInfo(input));
            if (detection is null)
            {
                Console.Error.WriteLine("Input must be an AXXX folder or a folder containing AXXX folders.");
                return 2;
            }

            var options = new DbCompileOptions(
                output,
                CategoryResolver.FromIndex(categoryIndex),
                parsed.HasFlag("decimal"),
                parsed.HasFlag("ignore-incomplete"),
                parsed.HasFlag("use-number"),
                parsed.HasFlag("json"),
                parsed.HasFlag("zip"),
                parsed.HasFlag("zip-track"),
                parsed.HasFlag("collection"),
                parsed.GetValue("music"),
                parsed.GetValue("cover"),
                parsed.GetValue("video")
            );

            var outputRoot = new DirectoryInfo(resolvedOutput);

            if (detection.ModeType == "single" && detection.AxxxPath is not null)
            {
                ProcessAxxx(detection.AxxxPath, outputRoot, options);
                return 0;
            }

            foreach (var axxx in detection.AxxxPaths)
            {
                var perAxxxOutput = new DirectoryInfo(Path.Combine(outputRoot.FullName, axxx.Name));
                ProcessAxxx(axxx, perAxxxOutput, options);
            }

            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 2;
        }
    }

    public void PrintHelp()
    {
        Console.WriteLine("db-compile");
        Console.WriteLine("  --input <AXXX or batch root>  (alias: -p, --path)");
        Console.WriteLine("  --output <folder>             (alias: -o) subfolder auto-created");
        Console.WriteLine("  --category <0-6>              (alias: -g, --genre)");
        Console.WriteLine("  --music <folder>              (alias: -m)");
        Console.WriteLine("  --cover <folder>              (alias: -c)");
        Console.WriteLine("  --video <folder>              (alias: -v)");
        Console.WriteLine("  --decimal                     (alias: -d)");
        Console.WriteLine("  --ignore-incomplete           (alias: -i, --ignore)");
        Console.WriteLine("  --use-number                  (alias: -n, --number)");
        Console.WriteLine("  --json                        (alias: -j)");
        Console.WriteLine("  --zip                         (per-category zip; deletes folders)");
        Console.WriteLine("  --zip-track                   (alias: -z; per-track zip)");
        Console.WriteLine("  --collection                  (alias: -k)");
    }

    private static IReadOnlyList<OptionSpec> GetOptionSpecs()
    {
        return
        [
            new OptionSpec("input", true, "p", "path"),
            new OptionSpec("output", true, "o", "output"),
            new OptionSpec("format", true, "f", "format"),
            new OptionSpec("category", true, "g", "genre", "category"),
            new OptionSpec("music", true, "m", "music"),
            new OptionSpec("cover", true, "c", "cover"),
            new OptionSpec("video", true, "v", "video"),
            new OptionSpec("decimal", false, "d", "decimal"),
            new OptionSpec("ignore-incomplete", false, "i", "ignore"),
            new OptionSpec("use-number", false, "n", "number"),
            new OptionSpec("json", false, "j", "json"),
            new OptionSpec("zip", false, "zip"),
            new OptionSpec("zip-track", false, "z", "zip-track"),
            new OptionSpec("collection", false, "k", "collection"),
        ];
    }

    private static void ProcessAxxx(DirectoryInfo axxxRoot, DirectoryInfo outputRoot, DbCompileOptions options)
    {
        if (!axxxRoot.Exists)
        {
            throw new DirectoryNotFoundException(axxxRoot.FullName);
        }

        if (!EnsureOutputReady(outputRoot))
        {
            return;
        }

        var musicRoot = new DirectoryInfo(Path.Combine(axxxRoot.FullName, "music"));
        if (!musicRoot.Exists)
        {
            throw new DirectoryNotFoundException(musicRoot.FullName);
        }

        var compiledTracks = new Dictionary<int, string>();
        var compiledMetadata = new List<TrackMetadata>();
        var warnings = new List<string>();
        var trackFolders = musicRoot.GetDirectories();

        foreach (var trackFolder in trackFolders)
        {
            var ma2Files = trackFolder.GetFiles("*.ma2");
            if (ma2Files.Length == 0)
            {
                continue;
            }

            var xmlPath = Path.Combine(trackFolder.FullName, "Music.xml");
            if (!File.Exists(xmlPath))
            {
                continue;
            }

            var info = new XmlInformation(trackFolder.FullName + Path.DirectorySeparatorChar);
            var trackMeta = BuildMetadata(info);
            var categoryName = CategoryResolver.GetCategoryName(options.CategoryMethod, trackMeta);
            var categoryPath = string.IsNullOrWhiteSpace(categoryName)
                ? outputRoot.FullName
                : Path.Combine(outputRoot.FullName, categoryName);
            var categoryDir = new DirectoryInfo(categoryPath);
            if (!categoryDir.Exists)
            {
                categoryDir.Create();
            }

            var sanitizedSort = SanitizePathSegment(info.TrackSortName);
            var baseName = options.UseNumber || string.IsNullOrWhiteSpace(sanitizedSort)
                ? info.TrackID
                : $"{info.TrackID}-{sanitizedSort}";
            var dxSuffix = info.IsDXChart ? "-DX" : string.Empty;
            var trackFolderName = $"{baseName}{dxSuffix}";

            var targetPath = Path.Combine(categoryDir.FullName, trackFolderName);
            var targetDir = new DirectoryInfo(targetPath);
            if (!targetDir.Exists)
            {
                targetDir.Create();
            }

            var hasUtage = info.InformationDict.TryGetValue("Utage", out var utageValue) &&
                           !string.IsNullOrWhiteSpace(utageValue);
            if (hasUtage)
            {
                targetDir = new DirectoryInfo(targetPath + "-Utage");
                if (!targetDir.Exists)
                {
                    targetDir.Create();
                }
            }

            var compiler = new SimaiCompiler(options.StrictDecimal, trackFolder.FullName + Path.DirectorySeparatorChar,
                targetDir.FullName, hasUtage);
            var maidata = MaidataCustomizer.ApplyBranding(compiler.Result, BrandingInfo.Default);
            File.WriteAllText(Path.Combine(targetDir.FullName, "maidata.txt"), maidata);

            var incomplete = false;
            var missingAssets = new List<string>();
            if (!string.IsNullOrWhiteSpace(options.MusicRoot))
            {
                var audioSource = AssetNaming.BuildAudioPath(options.MusicRoot!, info.TrackID);
                var audioTarget = Path.Combine(targetDir.FullName, "track.mp3");
                if (!File.Exists(audioSource))
                {
                    warnings.Add($"Music not found: {info.TrackName} at {audioSource}");
                    incomplete = true;
                    missingAssets.Add("music");
                }
                else if (!File.Exists(audioTarget))
                {
                    File.Copy(audioSource, audioTarget, false);
                }
            }

            if (!string.IsNullOrWhiteSpace(options.CoverRoot))
            {
                var imageSource = AssetNaming.BuildImagePath(options.CoverRoot!, info.TrackID);
                var imageTarget = Path.Combine(targetDir.FullName, "bg.png");
                if (!File.Exists(imageSource))
                {
                    warnings.Add($"Image not found: {info.TrackName} at {imageSource}");
                    incomplete = true;
                    missingAssets.Add("cover");
                }
                else if (!File.Exists(imageTarget))
                {
                    File.Copy(imageSource, imageTarget, false);
                }
            }

            if (!string.IsNullOrWhiteSpace(options.VideoRoot))
            {
                var videoSource = AssetNaming.BuildVideoPath(options.VideoRoot!, info.TrackID);
                var videoTarget = Path.Combine(targetDir.FullName, "pv.mp4");
                if (!File.Exists(videoSource))
                {
                    warnings.Add($"Video not found: {info.TrackName} at {videoSource}");
                    incomplete = true;
                    missingAssets.Add("video");
                }
                else if (!File.Exists(videoTarget))
                {
                    File.Copy(videoSource, videoTarget, false);
                }
            }

            if (incomplete)
            {
                if (!options.IgnoreIncomplete)
                {
                    var shouldContinue = PromptContinueMissing(info.TrackName, missingAssets);
                    if (!shouldContinue)
                    {
                        throw new FileNotFoundException("Conversion cancelled due to missing assets.");
                    }
                }

                var incompleteDir = new DirectoryInfo(targetDir.FullName + "_Incomplete");
                if (targetDir.Exists)
                {
                    targetDir.MoveTo(incompleteDir.FullName);
                }
                continue;
            }

            if (int.TryParse(info.TrackID, out var trackId))
            {
                compiledTracks[trackId] = info.TrackName;
            }
            compiledMetadata.Add(trackMeta);

            if (options.ZipTrack)
            {
                ZipService.ZipFolderAndMaybeDelete(targetDir, true);
            }
        }

        LogWriter.WriteTextLog(outputRoot, compiledTracks, warnings);
        if (options.JsonLog)
        {
            LogWriter.WriteJsonIndex(outputRoot, compiledTracks);
        }

        if (options.Collection)
        {
            var collectionDir = new DirectoryInfo(Path.Combine(outputRoot.FullName, "collections"));
            CollectionManifestWriter.WriteCollections(collectionDir, compiledMetadata);
        }

        if (options.ZipCategory)
        {
            foreach (var dir in outputRoot.EnumerateDirectories())
            {
                if (dir.Name.Equals("collections", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                ZipService.ZipFolderAndMaybeDelete(dir, true);
            }
        }
    }

    private static bool EnsureOutputReady(DirectoryInfo outputRoot)
    {
        if (!outputRoot.Exists)
        {
            outputRoot.Create();
            return true;
        }

        if (!outputRoot.EnumerateFileSystemInfos().Any())
        {
            return true;
        }

        if (!PromptYesNo($"Output folder has contents: {outputRoot.FullName}. Overwrite? (y/n): "))
        {
            Console.WriteLine("Skipped due to existing output.");
            return false;
        }

        foreach (var entry in outputRoot.EnumerateFileSystemInfos())
        {
            switch (entry)
            {
                case FileInfo file:
                    file.Delete();
                    break;
                case DirectoryInfo dir:
                    dir.Delete(true);
                    break;
            }
        }

        return true;
    }

    private static bool PromptYesNo(string prompt)
    {
        while (true)
        {
            Console.Write(prompt);
            var input = Console.ReadLine()?.Trim().ToLowerInvariant();
            if (input is "y" or "yes")
            {
                return true;
            }

            if (input is "n" or "no")
            {
                return false;
            }
        }
    }

    private static bool PromptContinueMissing(string trackName, IReadOnlyList<string> missingAssets)
    {
        var missingText = missingAssets.Count > 0 ? string.Join(", ", missingAssets) : "assets";
        while (true)
        {
            Console.Write($"Missing {missingText} for '{trackName}'. Continue? (y/n): ");
            var input = Console.ReadLine()?.Trim().ToLowerInvariant();
            if (input is "y" or "yes")
            {
                return true;
            }

            if (input is "n" or "no")
            {
                return false;
            }
        }
    }

    private static string SanitizePathSegment(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var invalid = Path.GetInvalidFileNameChars();
        var cleaned = new string(value.Select(ch => invalid.Contains(ch) ? '_' : ch).ToArray());
        return cleaned.Trim();
    }

    private static TrackMetadata BuildMetadata(XmlInformation info)
    {
        return new TrackMetadata(
            info.TrackID,
            info.TrackName,
            info.TrackSortName,
            info.TrackGenre,
            info.TrackSymbolicLevel,
            info.TrackVersion,
            info.TrackComposer,
            info.TrackBPM,
            info.StandardDeluxePrefix,
            info.DXChartTrackPathSuffix
        );
    }

    private static string RequireValue(ParsedOptions parsed, string name)
    {
        var value = parsed.GetValue(name);
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException($"Missing required option: --{name}");
        }

        return value!;
    }

    private static int RequireInt(ParsedOptions parsed, string name)
    {
        var raw = RequireValue(parsed, name);
        if (!int.TryParse(raw, out var value))
        {
            throw new ArgumentException($"Option --{name} must be an integer.");
        }

        return value;
    }

    private sealed record DbCompileOptions(
        string OutputRoot,
        CategoryMethod CategoryMethod,
        bool StrictDecimal,
        bool IgnoreIncomplete,
        bool UseNumber,
        bool JsonLog,
        bool ZipCategory,
        bool ZipTrack,
        bool Collection,
        string? MusicRoot,
        string? CoverRoot,
        string? VideoRoot
    );
}
