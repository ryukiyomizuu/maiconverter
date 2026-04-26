using System.Text.RegularExpressions;

namespace MaiConverter.Custom.Core.Services;

public sealed record AxxxDetection(
    string ModeType,
    DirectoryInfo? AxxxPath,
    IReadOnlyList<DirectoryInfo> AxxxPaths,
    DirectoryInfo? BatchRoot
);

public static class AxxxDetector
{
    private static readonly Regex AxxxPattern = new("^[A-Z]\\d{3}$", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    public static bool IsAxxxFolderName(string name)
    {
        return AxxxPattern.IsMatch(name);
    }

    public static bool IsAxxxFolder(DirectoryInfo dir)
    {
        return dir.Exists && IsAxxxFolderName(dir.Name);
    }

    public static IReadOnlyList<DirectoryInfo> FindAxxxFolders(DirectoryInfo root)
    {
        if (!root.Exists)
        {
            return Array.Empty<DirectoryInfo>();
        }

        return root.EnumerateDirectories()
            .Where(d => IsAxxxFolderName(d.Name))
            .OrderBy(d => d.Name, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    public static AxxxDetection? Detect(DirectoryInfo input)
    {
        if (IsAxxxFolder(input))
        {
            return new AxxxDetection("single", input, new List<DirectoryInfo> { input }, null);
        }

        var children = FindAxxxFolders(input);
        if (children.Count > 0)
        {
            return new AxxxDetection("batch", null, children, input);
        }

        return null;
    }
}
