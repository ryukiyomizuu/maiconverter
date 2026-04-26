namespace MaiConverter.Custom.Cli.Parsing;

public sealed class ParsedOptions
{
    private readonly Dictionary<string, string?> values;

    public ParsedOptions(Dictionary<string, string?> values, IReadOnlyList<string> extraArgs)
    {
        this.values = values;
        ExtraArgs = extraArgs;
    }

    public IReadOnlyList<string> ExtraArgs { get; }

    public string? GetValue(string name)
    {
        return values.TryGetValue(name, out var value) ? value : null;
    }

    public bool HasFlag(string name)
    {
        return values.ContainsKey(name);
    }
}
