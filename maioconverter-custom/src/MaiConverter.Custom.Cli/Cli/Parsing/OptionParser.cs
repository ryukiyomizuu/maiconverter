namespace MaiConverter.Custom.Cli.Parsing;

public static class OptionParser
{
    public static ParsedOptions Parse(string[] args, IReadOnlyList<OptionSpec> specs)
    {
        var lookup = BuildLookup(specs);
        var values = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);
        var extras = new List<string>();

        for (var i = 0; i < args.Length; i++)
        {
            var token = args[i];
            if (string.IsNullOrWhiteSpace(token))
            {
                continue;
            }

            if (token.StartsWith("--", StringComparison.Ordinal))
            {
                var trimmed = token[2..];
                var split = trimmed.Split('=', 2, StringSplitOptions.RemoveEmptyEntries);
                var key = split[0];
                var spec = ResolveSpec(lookup, key);
                if (spec is null)
                {
                    throw new ArgumentException($"Unknown option: --{key}");
                }

                if (spec.RequiresValue)
                {
                    var value = split.Length > 1 ? split[1] : ReadNextValue(args, ref i, key);
                    values[spec.Name] = value;
                }
                else
                {
                    values[spec.Name] = "true";
                }

                continue;
            }

            if (token.StartsWith("-", StringComparison.Ordinal) && token.Length > 1)
            {
                var key = token[1..];
                var spec = ResolveSpec(lookup, key);
                if (spec is null)
                {
                    throw new ArgumentException($"Unknown option: -{key}");
                }

                if (spec.RequiresValue)
                {
                    var value = ReadNextValue(args, ref i, key);
                    values[spec.Name] = value;
                }
                else
                {
                    values[spec.Name] = "true";
                }

                continue;
            }

            extras.Add(token);
        }

        return new ParsedOptions(values, extras);
    }

    private static Dictionary<string, OptionSpec> BuildLookup(IEnumerable<OptionSpec> specs)
    {
        var lookup = new Dictionary<string, OptionSpec>(StringComparer.OrdinalIgnoreCase);
        foreach (var spec in specs)
        {
            lookup[spec.Name] = spec;
            foreach (var alias in spec.Aliases)
            {
                lookup[alias] = spec;
            }
        }

        return lookup;
    }

    private static OptionSpec? ResolveSpec(Dictionary<string, OptionSpec> lookup, string key)
    {
        return lookup.TryGetValue(key, out var spec) ? spec : null;
    }

    private static string ReadNextValue(string[] args, ref int index, string key)
    {
        if (index + 1 >= args.Length)
        {
            throw new ArgumentException($"Option '{key}' expects a value.");
        }

        index++;
        return args[index];
    }
}
