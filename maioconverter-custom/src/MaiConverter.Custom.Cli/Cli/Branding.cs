namespace MaiConverter.Custom.Cli;

public sealed record BrandingInfo(
    string ChartConverter,
    string ToolName,
    string ToolVersion,
    string Message
)
{
    public static BrandingInfo Default => new(
        "Ryuki",
        "Maimai Forge",
        "0.5",
        "Thanks for using! See [link] for more info!"
    );
}
