namespace MaiConverter.Custom.Cli;

public static class OutputPathHelper
{
    public static string? Resolve(string? outputRoot, string inputPath)
    {
        if (string.IsNullOrWhiteSpace(outputRoot))
        {
            return null;
        }

        var baseName = GetInputBaseName(inputPath);
        return Path.Combine(outputRoot, baseName);
    }

    private static string GetInputBaseName(string inputPath)
    {
        var trimmed = inputPath.Trim().Trim('"');
        var fullPath = Path.GetFullPath(trimmed);

        if (Directory.Exists(fullPath))
        {
            var name = Path.GetFileName(fullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
            if (!string.IsNullOrWhiteSpace(name))
            {
                return name;
            }
        }

        var fileName = Path.GetFileNameWithoutExtension(fullPath);
        return string.IsNullOrWhiteSpace(fileName) ? "output" : fileName;
    }
}
