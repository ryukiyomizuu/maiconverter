namespace MaiConverter.Custom.Core.Models;

public sealed record TrackMetadata(
    string TrackId,
    string TrackName,
    string TrackSortName,
    string TrackGenre,
    string TrackSymbolicLevel,
    string TrackVersion,
    string TrackComposer,
    string TrackBpm,
    string StandardDeluxePrefix,
    string DxChartTrackPathSuffix
);
