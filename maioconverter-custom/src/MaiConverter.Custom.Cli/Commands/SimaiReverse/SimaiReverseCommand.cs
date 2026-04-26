using MaiConverter.Custom.Cli.Parsing;
using MaiConverter.Custom.Core.Services;

namespace MaiConverter.Custom.Cli.Commands.SimaiReverse;

public sealed class SimaiReverseCommand : ICommand
{
    public string Name => "simai-reverse";
    public IReadOnlyList<string> Aliases => ["ReverseMa2FromSimaiDatabase"];
    public string Description => "Reverse a Simai database into MaiAnalysis-style assets.";

    public int Run(string[] args)
    {
        try
        {
            var parsed = OptionParser.Parse(args, GetOptionSpecs());
            var input = RequireValue(parsed, "input");
            var output = parsed.GetValue("output");
            var overwrite = parsed.HasFlag("overwrite");

            var sourceDir = new DirectoryInfo(input);
            if (!sourceDir.Exists)
            {
                throw new DirectoryNotFoundException(sourceDir.FullName);
            }

            var destination = string.IsNullOrWhiteSpace(output)
                ? Path.Combine(sourceDir.FullName, "MaiAnalysis")
                : OutputPathHelper.Resolve(output, input) ?? output!;

            var destDir = new DirectoryInfo(destination);
            if (!destDir.Exists)
            {
                destDir.Create();
            }

            var soundDir = EnsureDir(destDir, "Sound");
            var imageDir = EnsureDir(destDir, Path.Combine("Image", "Texture2D"));
            var videoDir = EnsureDir(destDir, "DXBGA");

            var allFolders = Directory.GetDirectories(sourceDir.FullName, "", SearchOption.AllDirectories);
            foreach (var folder in allFolders)
            {
                var folderName = Path.GetFileName(folder);
                var idCandidate = folderName.Split('_')[0];
                if (!int.TryParse(idCandidate, out var id))
                {
                    continue;
                }

                var id6 = AssetNaming.NormalizeId6(id.ToString());
                CopyIfExists(Path.Combine(folder, "bg.png"), Path.Combine(imageDir.FullName, $"UI_Jacket_{id6}.png"),
                    overwrite);
                CopyIfExists(Path.Combine(folder, "pv.mp4"), Path.Combine(videoDir.FullName, $"{id6}.mp4"),
                    overwrite);
                CopyIfExists(Path.Combine(folder, "mv.mp4"), Path.Combine(videoDir.FullName, $"{id6}.mp4"),
                    overwrite);
                CopyIfExists(Path.Combine(folder, "track.mp3"), Path.Combine(soundDir.FullName, $"music{id6}.mp3"),
                    overwrite);
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
        Console.WriteLine("simai-reverse");
        Console.WriteLine("  --input <folder>   (alias: -p, --path)");
        Console.WriteLine("  --output <folder>  (alias: -o) subfolder auto-created");
        Console.WriteLine("  --overwrite        (alias: -r, --replace)");
    }

    private static IReadOnlyList<OptionSpec> GetOptionSpecs()
    {
        return
        [
            new OptionSpec("input", true, "p", "path"),
            new OptionSpec("output", true, "o", "output"),
            new OptionSpec("overwrite", false, "r", "replace"),
        ];
    }

    private static DirectoryInfo EnsureDir(DirectoryInfo root, string relative)
    {
        var dir = new DirectoryInfo(Path.Combine(root.FullName, relative));
        if (!dir.Exists)
        {
            dir.Create();
        }

        return dir;
    }

    private static void CopyIfExists(string source, string destination, bool overwrite)
    {
        if (!File.Exists(source))
        {
            return;
        }

        if (File.Exists(destination) && !overwrite)
        {
            return;
        }

        File.Copy(source, destination, overwrite);
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
}
