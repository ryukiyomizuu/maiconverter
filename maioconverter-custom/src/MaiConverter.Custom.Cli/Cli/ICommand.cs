namespace MaiConverter.Custom.Cli;

public interface ICommand
{
    string Name { get; }
    IReadOnlyList<string> Aliases { get; }
    string Description { get; }
    int Run(string[] args);
    void PrintHelp();
}
