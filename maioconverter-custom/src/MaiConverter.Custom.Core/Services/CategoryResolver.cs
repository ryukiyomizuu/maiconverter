using MaiConverter.Custom.Core.Enums;
using MaiConverter.Custom.Core.Models;

namespace MaiConverter.Custom.Core.Services;

public static class CategoryResolver
{
    public static CategoryMethod FromIndex(int index)
    {
        if (index < 0 || index > 6)
        {
            throw new ArgumentOutOfRangeException(nameof(index), "Category index must be 0-6.");
        }

        return (CategoryMethod)index;
    }

    public static string GetCategoryName(CategoryMethod method, TrackMetadata track)
    {
        return method switch
        {
            CategoryMethod.Genre => track.TrackGenre,
            CategoryMethod.Level => track.TrackSymbolicLevel,
            CategoryMethod.Cabinet => track.TrackVersion,
            CategoryMethod.Composer => track.TrackComposer,
            CategoryMethod.BPM => track.TrackBpm,
            CategoryMethod.SdDx => track.StandardDeluxePrefix,
            CategoryMethod.None => string.Empty,
            _ => string.Empty,
        };
    }
}
