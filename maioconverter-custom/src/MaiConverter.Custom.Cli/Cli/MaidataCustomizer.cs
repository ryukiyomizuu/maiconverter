namespace MaiConverter.Custom.Cli;

public static class MaidataCustomizer
{
    public static string ApplyBranding(string content, BrandingInfo branding)
    {
        if (string.IsNullOrEmpty(content))
        {
            return content;
        }

        var normalized = content.Replace("\r\n", "\n");
        var lines = normalized.Split('\n');
        var output = new List<string>(lines.Length + 4);

        var hasConverter = false;
        var hasTool = false;
        var hasToolVersion = false;
        var hasMsg = false;

        foreach (var line in lines)
        {
            if (line.StartsWith("&ChartConverter=", StringComparison.OrdinalIgnoreCase))
            {
                output.Add($"&ChartConverter={branding.ChartConverter}");
                hasConverter = true;
                continue;
            }

            if (line.StartsWith("&ChartConvertTool=", StringComparison.OrdinalIgnoreCase))
            {
                output.Add($"&Tool={branding.ToolName}");
                hasTool = true;
                continue;
            }

            if (line.StartsWith("&ChartConvertToolVersion=", StringComparison.OrdinalIgnoreCase))
            {
                output.Add($"&ToolVersion={branding.ToolVersion}");
                hasToolVersion = true;
                continue;
            }

            if (line.StartsWith("&smsg=", StringComparison.OrdinalIgnoreCase))
            {
                output.Add($"&msg={branding.Message}");
                hasMsg = true;
                continue;
            }

            output.Add(line);
        }

        if (!hasConverter || !hasTool || !hasToolVersion || !hasMsg)
        {
            var insertIndex = output.FindIndex(string.IsNullOrWhiteSpace);
            if (insertIndex < 0)
            {
                insertIndex = output.Count;
            }

            var inserts = new List<string>();
            if (!hasConverter)
            {
                inserts.Add($"&ChartConverter={branding.ChartConverter}");
            }
            if (!hasTool)
            {
                inserts.Add($"&Tool={branding.ToolName}");
            }
            if (!hasToolVersion)
            {
                inserts.Add($"&ToolVersion={branding.ToolVersion}");
            }
            if (!hasMsg)
            {
                inserts.Add($"&msg={branding.Message}");
            }

            output.InsertRange(insertIndex, inserts);
        }

        return string.Join(Environment.NewLine, output);
    }
}
