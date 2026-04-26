using System.IO.Compression;

namespace MaiConverter.Custom.Core.Services;

public static class ZipService
{
    public static void ZipDirectory(DirectoryInfo sourceDir, FileInfo zipFile, bool overwrite = true)
    {
        if (!sourceDir.Exists)
        {
            throw new DirectoryNotFoundException(sourceDir.FullName);
        }

        if (zipFile.Exists)
        {
            if (!overwrite)
            {
                return;
            }

            zipFile.Delete();
        }

        ZipFile.CreateFromDirectory(sourceDir.FullName, zipFile.FullName);
    }

    public static void ZipFolderAndMaybeDelete(DirectoryInfo sourceDir, bool deleteAfter, bool overwrite = true)
    {
        var zipPath = new FileInfo($"{sourceDir.FullName}.zip");
        ZipDirectory(sourceDir, zipPath, overwrite);
        if (deleteAfter)
        {
            sourceDir.Delete(true);
        }
    }

    public static IReadOnlyList<FileInfo> ZipImmediateSubfolders(DirectoryInfo outputRoot, bool deleteAfter, bool overwrite = true)
    {
        if (!outputRoot.Exists)
        {
            return Array.Empty<FileInfo>();
        }

        var zips = new List<FileInfo>();
        foreach (var dir in outputRoot.EnumerateDirectories())
        {
            var zipPath = new FileInfo($"{dir.FullName}.zip");
            ZipDirectory(dir, zipPath, overwrite);
            zips.Add(zipPath);
            if (deleteAfter)
            {
                dir.Delete(true);
            }
        }

        return zips;
    }
}
