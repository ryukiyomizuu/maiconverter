using System;
using MaiConverter.Custom.Cli.Commands.DbCompile;
using MaiConverter.Custom.Cli.Commands.Ma2ById;
using MaiConverter.Custom.Cli.Commands.Ma2Compile;
using MaiConverter.Custom.Cli.Commands.SimaiCompile;
using MaiConverter.Custom.Cli.Commands.SimaiReverse;

namespace MaiConverter.Custom.Cli;

internal static class Program
{
    public static int Main(string[] args)
    {
        var commands = new ICommand[]
        {
            new DbCompileCommand(),
            new Ma2CompileCommand(),
            new Ma2ByIdCommand(),
            new SimaiCompileCommand(),
            new SimaiReverseCommand(),
        };

        var registry = new CommandRegistry(commands);
        if (args.Length == 0 || args[0] is "help" or "--help" or "-h")
        {
            PrintHelp(registry);
            return 0;
        }

        var commandName = args[0];
        var command = registry.Find(commandName);
        if (command is null)
        {
            Console.Error.WriteLine($"Unknown command: {commandName}");
            PrintHelp(registry);
            return 2;
        }

        var commandArgs = args.Skip(1).ToArray();
        if (commandArgs.Contains("--help") || commandArgs.Contains("-h"))
        {
            command.PrintHelp();
            return 0;
        }

        return command.Run(commandArgs);
    }

    private static void PrintHelp(CommandRegistry registry)
    {
        Console.WriteLine("Maimai Forge — Custom Converter");
        Console.WriteLine("Commands:");
        foreach (var cmd in registry.AllCommands.OrderBy(c => c.Name))
        {
            Console.WriteLine($"  {cmd.Name} - {cmd.Description}");
        }
        Console.WriteLine();
        Console.WriteLine("Use '<command> --help' to see command options.");
    }
}
