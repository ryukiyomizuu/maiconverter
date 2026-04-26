namespace MaiConverter.Custom.Core.Services;

public static class AssetNaming
{
    public static string NormalizeId6(string input)
    {
        if (string.IsNullOrWhiteSpace(input))
        {
            throw new ArgumentException("Track ID cannot be empty.", nameof(input));
        }

        var digits = new string(input.Where(char.IsDigit).ToArray());
        var baseId = string.IsNullOrEmpty(digits) ? input.Trim() : digits;
        if (baseId.Length > 6)
        {
            baseId = baseId[^6..];
        }

        return baseId.PadLeft(6, '0');
    }

    public static string ShortId4(string input)
    {
        var normalized = NormalizeId6(input);
        return normalized.Substring(2, 4);
    }

    public static string AudioFileName(string trackId)
    {
        return $"music00{ShortId4(trackId)}.mp3";
    }

    public static string ImageFileName(string trackId)
    {
        return $"UI_Jacket_00{ShortId4(trackId)}.png";
    }

    public static string VideoFileName(string trackId)
    {
        return $"{ShortId4(trackId)}.mp4";
    }

    public static string BuildAudioPath(string audioRoot, string trackId)
    {
        return Path.Combine(audioRoot, AudioFileName(trackId));
    }

    public static string BuildImagePath(string imageRoot, string trackId)
    {
        return Path.Combine(imageRoot, ImageFileName(trackId));
    }

    public static string BuildVideoPath(string videoRoot, string trackId)
    {
        return Path.Combine(videoRoot, VideoFileName(trackId));
    }
}
