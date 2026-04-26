using MaiConverter.Custom.Cli.Parsing;
using MaiConverter.Custom.Core.Services;
using MaiLib;

namespace MaiConverter.Custom.Cli.Commands.Ma2ById;

public sealed class Ma2ByIdCommand : ICommand
{
    public string Name => "ma2-by-id";
    public IReadOnlyList<string> Aliases => ["CompileMa2ID"];
    public string Description => "Compile a MA2 chart by music ID from an AXXX root.";

    public int Run(string[] args)
    {
        try
        {
            var parsed = OptionParser.Parse(args, GetOptionSpecs());
            var input = RequireValue(parsed, "input");
            var output = OutputPathHelper.Resolve(parsed.GetValue("output"), input);
            var format = parsed.GetValue("format");
            var difficulty = RequireValue(parsed, "difficulty");
            var trackId = RequireValue(parsed, "id");
            var rotate = parsed.GetValue("rotate");
            var shift = parsed.GetValue("shift");

            var rootDir = new DirectoryInfo(input);
            if (!rootDir.Exists)
            {
                throw new DirectoryNotFoundException(rootDir.FullName);
            }

            var normalizedId = AssetNaming.NormalizeId6(trackId);
            var ma2Path = Path.Combine(rootDir.FullName, "music", $"music{normalizedId}",
                $"{normalizedId}_0{difficulty}.ma2");
            if (!File.Exists(ma2Path))
            {
                Console.WriteLine($"MA2 file not found, skipping: {ma2Path}");
                return 0;
            }

            var tokenizer = new Ma2Tokenizer();
            var parser = new Ma2Parser();
            var candidate = parser.ChartOfToken(tokenizer.Tokens(ma2Path));

            if (!string.IsNullOrWhiteSpace(rotate))
            {
                if (!Enum.TryParse(rotate, true, out NoteEnum.FlipMethod rotateMethod))
                {
                    throw new ArgumentException($"Invalid rotate method: {rotate}");
                }
                candidate.RotateNotes(rotateMethod);
            }

            if (!string.IsNullOrWhiteSpace(shift) && int.TryParse(shift, out var shiftTick) && shiftTick != 0)
            {
                candidate.ShiftByOffset(shiftTick);
            }

            if (IsSimaiFormat(format))
            {
                var resultChart = new Simai(candidate);
                var result = MaidataCustomizer.ApplyBranding(resultChart.Compose(), BrandingInfo.Default);
                WriteOutput(output, "maidata.txt", result);
                return 0;
            }

            var ma2Chart = CreateMa2Chart(candidate, format);
            var ma2Result = ma2Chart.Compose();
            WriteOutput(output, "result.ma2", ma2Result);
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
        Console.WriteLine("ma2-by-id");
        Console.WriteLine("  --input <AXXX root>   (alias: -p, --path)");
        Console.WriteLine("  --id <music id>       (alias: -i)");
        Console.WriteLine("  --difficulty <0-4>    (alias: -d)");
        Console.WriteLine("  --output <folder>     (alias: -o) subfolder auto-created");
        Console.WriteLine("  --format <format>     (alias: -f)");
        Console.WriteLine("  --rotate <method>     (alias: -r)");
        Console.WriteLine("  --shift <ticks>       (alias: -s)");
    }

    private static IReadOnlyList<OptionSpec> GetOptionSpecs()
    {
        return
        [
            new OptionSpec("input", true, "p", "path"),
            new OptionSpec("output", true, "o", "output"),
            new OptionSpec("format", true, "f", "format"),
            new OptionSpec("difficulty", true, "d", "difficulty"),
            new OptionSpec("id", true, "i", "id"),
            new OptionSpec("rotate", true, "r", "rotate"),
            new OptionSpec("shift", true, "s", "shift"),
        ];
    }

    private static void WriteOutput(string? outputDir, string fileName, string content)
    {
        if (string.IsNullOrWhiteSpace(outputDir))
        {
            Console.WriteLine(content);
            return;
        }

        var dir = new DirectoryInfo(outputDir);
        if (!dir.Exists)
        {
            dir.Create();
        }

        var target = Path.Combine(dir.FullName, fileName);
        File.WriteAllText(target, content);
    }

    private static bool IsSimaiFormat(string? format)
    {
        if (string.IsNullOrWhiteSpace(format))
        {
            return true;
        }

        return format.Equals("simai", StringComparison.OrdinalIgnoreCase) ||
               format.Equals("simaifes", StringComparison.OrdinalIgnoreCase);
    }

    private static Ma2 CreateMa2Chart(Chart candidate, string? format)
    {
        if (!string.IsNullOrWhiteSpace(format) &&
            format.Equals("ma2_104", StringComparison.OrdinalIgnoreCase))
        {
            return new Ma2(candidate) { ChartVersion = ChartEnum.ChartVersion.Ma2_104 };
        }

        if (!string.IsNullOrWhiteSpace(format) &&
            format.Equals("ma2_105", StringComparison.OrdinalIgnoreCase))
        {
            return new Ma2(candidate) { ChartVersion = ChartEnum.ChartVersion.Ma2_105 };
        }

        return new Ma2(candidate);
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
