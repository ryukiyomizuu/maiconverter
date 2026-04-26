using MaiConverter.Custom.Cli.Parsing;
using MaiLib;

namespace MaiConverter.Custom.Cli.Commands.Ma2Compile;

public sealed class Ma2CompileCommand : ICommand
{
    public string Name => "ma2-compile";
    public IReadOnlyList<string> Aliases => ["CompileMa2"];
    public string Description => "Compile a single MA2 chart to Simai or MA2 output.";

    public int Run(string[] args)
    {
        try
        {
            var parsed = OptionParser.Parse(args, GetOptionSpecs());
            var input = RequireValue(parsed, "input");
            var output = OutputPathHelper.Resolve(parsed.GetValue("output"), input);
            var format = parsed.GetValue("format");
            var rotate = parsed.GetValue("rotate");
            var shift = parsed.GetValue("shift");

            if (!File.Exists(input))
            {
                throw new FileNotFoundException(input);
            }

            var tokenizer = new Ma2Tokenizer();
            var parser = new Ma2Parser();
            var candidate = parser.ChartOfToken(tokenizer.Tokens(input));

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
        Console.WriteLine("ma2-compile");
        Console.WriteLine("  --input <ma2 file>   (alias: -p, --path)");
        Console.WriteLine("  --output <folder>    (alias: -o) subfolder auto-created");
        Console.WriteLine("  --format <format>    (alias: -f)");
        Console.WriteLine("  --rotate <method>    (alias: -r)");
        Console.WriteLine("  --shift <ticks>      (alias: -s)");
    }

    private static IReadOnlyList<OptionSpec> GetOptionSpecs()
    {
        return
        [
            new OptionSpec("input", true, "p", "path"),
            new OptionSpec("output", true, "o", "output"),
            new OptionSpec("format", true, "f", "format"),
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
