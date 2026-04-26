namespace MaiConverter.Custom.Cli;

public sealed class CommandRegistry
{
    private readonly Dictionary<string, ICommand> lookup;

    public CommandRegistry(IEnumerable<ICommand> commands)
    {
        lookup = new Dictionary<string, ICommand>(StringComparer.OrdinalIgnoreCase);
        foreach (var command in commands)
        {
            lookup[command.Name] = command;
            foreach (var alias in command.Aliases)
            {
                lookup[alias] = command;
            }
        }
    }

    public ICommand? Find(string name)
    {
        return lookup.TryGetValue(name, out var command) ? command : null;
    }

    public IReadOnlyCollection<ICommand> AllCommands => lookup.Values.Distinct().ToList();
}
