namespace MaiConverter.Custom.Cli.Parsing;

public sealed class OptionSpec
{
    public OptionSpec(string name, bool requiresValue, params string[] aliases)
    {
        Name = name ?? throw new ArgumentNullException(nameof(name));
        RequiresValue = requiresValue;
        Aliases = aliases?.ToList() ?? [];
    }

    public string Name { get; }
    public bool RequiresValue { get; }
    public IReadOnlyList<string> Aliases { get; }
}
