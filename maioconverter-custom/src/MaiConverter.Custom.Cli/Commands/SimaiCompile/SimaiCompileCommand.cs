using MaiConverter.Custom.Cli.Parsing;
using MaiLib;

namespace MaiConverter.Custom.Cli.Commands.SimaiCompile;

public sealed class SimaiCompileCommand : ICommand
{
    public string Name => "simai-compile";
    public IReadOnlyList<string> Aliases => ["CompileSimai"];
    public string Description => "Compile a Simai chart to MA2 or Simai output.";

    public int Run(string[] args)
    {
        try
        {
            var parsed = OptionParser.Parse(args, GetOptionSpecs());
            var input = RequireValue(parsed, "input");
            var output = OutputPathHelper.Resolve(parsed.GetValue("output"), input);
            var format = parsed.GetValue("format");
            var difficulty = parsed.GetValue("difficulty");
            var rotate = parsed.GetValue("rotate");
            var shift = parsed.GetValue("shift");

            if (!File.Exists(input))
            {
                throw new FileNotFoundException(input);
            }

            var tokenizer = new SimaiTokenizer();
            tokenizer.UpdateFromPath(input);
            var parser = new SimaiParser();
            var tokens = ResolveTokens(tokenizer, difficulty);
            var candidate = parser.ChartOfToken(tokens);

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
        Console.WriteLine("simai-compile");
        Console.WriteLine("  --input <simai file>   (alias: -p, --path)");
        Console.WriteLine("  --output <folder>      (alias: -o) subfolder auto-created");
        Console.WriteLine("  --format <format>      (alias: -f)");
        Console.WriteLine("  --difficulty <1-7>     (alias: -d)");
        Console.WriteLine("  --rotate <method>      (alias: -r)");
        Console.WriteLine("  --shift <ticks>        (alias: -s)");
    }

    private static IReadOnlyList<OptionSpec> GetOptionSpecs()
    {
        return
        [
            new OptionSpec("input", true, "p", "path"),
            new OptionSpec("output", true, "o", "output"),
            new OptionSpec("format", true, "f", "format"),
            new OptionSpec("difficulty", true, "d", "difficulty"),
            new OptionSpec("rotate", true, "r", "rotate"),
            new OptionSpec("shift", true, "s", "shift"),
        ];
    }

    private static string[] ResolveTokens(SimaiTokenizer tokenizer, string? difficulty)
    {
        if (string.IsNullOrWhiteSpace(difficulty))
        {
            return tokenizer.ChartCandidates.Values.First();
        }

        if (!tokenizer.ChartCandidates.TryGetValue(difficulty, out var tokens))
        {
            throw new ArgumentException($"Difficulty not found: {difficulty}");
        }

        return tokens;
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
            return false;
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
