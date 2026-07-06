"""YouTube tools - allows the agent to search and get info from YouTube."""

from typing import Any
from pydantic import BaseModel
import os
import requests
import re

from app.ai.tools.base import Tool, ToolParameter
from app.google.oauth import load_credentials
from googleapiclient.discovery import build


def get_youtube_api_key() -> str | None:
    """Get YouTube API key from environment (same as Maps)."""
    return os.getenv("GOOGLE_MAPS_API_KEY")


class YouTubeVideo(BaseModel):
    """Represents a YouTube video."""
    video_id: str
    title: str
    channel_name: str
    description: str
    published_at: str
    thumbnail_url: str | None = None
    video_url: str


class SearchYouTubeResult(BaseModel):
    """Result of searching YouTube videos."""
    success: bool
    query: str
    videos: list[YouTubeVideo] = []
    count: int
    message: str


class SearchYouTubeTool(Tool):
    """Tool for searching YouTube videos."""

    @property
    def name(self) -> str:
        return "search_youtube"

    @property
    def description(self) -> str:
        return "search for YouTube videos by keyword or topic"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "query",
                "type": "string",
                "description": "search query (e.g., 'Python tutorial', 'cooking recipes', 'music video')",
                "required": True,
            },
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of results (default: 5, max: 10)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> SearchYouTubeResult:
        """
        Search for YouTube videos.

        Args:
            query: Search query
            max_results: Max results (default 5)

        Returns:
            SearchYouTubeResult with video list
        """
        query = kwargs.get("query", "").strip()
        max_results = min(kwargs.get("max_results", 5), 10)

        if not query:
            raise ValueError("Search query is required")

        api_key = get_youtube_api_key()
        if not api_key:
            return SearchYouTubeResult(
                success=False,
                query=query,
                count=0,
                message="YouTube API key is not configured. Please add GOOGLE_MAPS_API_KEY to your .env file."
            )

        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "key": api_key,
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return SearchYouTubeResult(
                    success=False,
                    query=query,
                    count=0,
                    message=f"YouTube API error: {data['error'].get('message', 'Unknown error')}"
                )

            videos = []
            for item in data.get("items", []):
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]

                videos.append(YouTubeVideo(
                    video_id=video_id,
                    title=snippet["title"],
                    channel_name=snippet["channelTitle"],
                    description=snippet["description"][:200] + "..." if len(snippet["description"]) > 200 else snippet["description"],
                    published_at=snippet["publishedAt"],
                    thumbnail_url=snippet["thumbnails"]["medium"]["url"],
                    video_url=f"https://www.youtube.com/watch?v={video_id}"
                ))

            return SearchYouTubeResult(
                success=True,
                query=query,
                videos=videos,
                count=len(videos),
                message=f"🎥 Found {len(videos)} video(s) for '{query}'"
            )

        except Exception as e:
            return SearchYouTubeResult(
                success=False,
                query=query,
                count=0,
                message=f"Failed to search YouTube: {str(e)}"
            )


class VideoDetailsResult(BaseModel):
    """Result of getting video details."""
    success: bool
    video_id: str | None = None
    title: str | None = None
    channel_name: str | None = None
    description: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    published_at: str | None = None
    duration: str | None = None
    video_url: str | None = None
    message: str


class GetVideoDetailsTool(Tool):
    """Tool for getting detailed information about a YouTube video."""

    @property
    def name(self) -> str:
        return "get_youtube_video_details"

    @property
    def description(self) -> str:
        return "get detailed information about a YouTube video including views, likes, and description"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "video_url_or_id",
                "type": "string",
                "description": "YouTube video URL or video ID (e.g., 'https://youtube.com/watch?v=dQw4w9WgXcQ' or 'dQw4w9WgXcQ')",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> VideoDetailsResult:
        """
        Get details about a YouTube video.

        Args:
            video_url_or_id: Video URL or ID

        Returns:
            VideoDetailsResult with video information
        """
        video_input = kwargs.get("video_url_or_id", "").strip()

        if not video_input:
            raise ValueError("Video URL or ID is required")

        # Extract video ID from URL if needed
        video_id = video_input
        if "youtube.com" in video_input or "youtu.be" in video_input:
            # Extract ID from various YouTube URL formats
            patterns = [
                r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
                r'youtu\.be/([0-9A-Za-z_-]{11})',
            ]
            for pattern in patterns:
                match = re.search(pattern, video_input)
                if match:
                    video_id = match.group(1)
                    break

        api_key = get_youtube_api_key()
        if not api_key:
            return VideoDetailsResult(
                success=False,
                message="YouTube API key is not configured. Please add GOOGLE_MAPS_API_KEY to your .env file."
            )

        try:
            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                "part": "snippet,statistics,contentDetails",
                "id": video_id,
                "key": api_key,
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return VideoDetailsResult(
                    success=False,
                    message=f"YouTube API error: {data['error'].get('message', 'Unknown error')}"
                )

            if not data.get("items"):
                return VideoDetailsResult(
                    success=False,
                    video_id=video_id,
                    message=f"Video not found: {video_id}"
                )

            video = data["items"][0]
            snippet = video["snippet"]
            statistics = video.get("statistics", {})
            content_details = video.get("contentDetails", {})

            view_count = int(statistics.get("viewCount", 0))
            like_count = int(statistics.get("likeCount", 0))
            comment_count = int(statistics.get("commentCount", 0))

            message = f"🎥 {snippet['title']}\n"
            message += f"👤 Channel: {snippet['channelTitle']}\n"
            message += f"👁️ Views: {view_count:,}\n"
            message += f"👍 Likes: {like_count:,}\n"
            message += f"💬 Comments: {comment_count:,}\n"
            message += f"📅 Published: {snippet['publishedAt'][:10]}"

            return VideoDetailsResult(
                success=True,
                video_id=video_id,
                title=snippet["title"],
                channel_name=snippet["channelTitle"],
                description=snippet["description"][:500] + "..." if len(snippet["description"]) > 500 else snippet["description"],
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
                published_at=snippet["publishedAt"],
                duration=content_details.get("duration"),
                video_url=f"https://www.youtube.com/watch?v={video_id}",
                message=message
            )

        except Exception as e:
            return VideoDetailsResult(
                success=False,
                video_id=video_id,
                message=f"Failed to get video details: {str(e)}"
            )


class TrendingVideosResult(BaseModel):
    """Result of getting trending videos."""
    success: bool
    videos: list[YouTubeVideo] = []
    count: int
    message: str


class GetTrendingVideosTool(Tool):
    """Tool for getting trending YouTube videos."""

    @property
    def name(self) -> str:
        return "get_trending_youtube_videos"

    @property
    def description(self) -> str:
        return "get currently trending videos on YouTube"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of results (default: 5, max: 10)",
                "required": False,
            },
            {
                "name": "region_code",
                "type": "string",
                "description": "region code for trending videos (e.g., 'US', 'GB', 'IN'). Default: 'US'",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> TrendingVideosResult:
        """
        Get trending YouTube videos.

        Args:
            max_results: Max results (default 5)
            region_code: Region code (default 'US')

        Returns:
            TrendingVideosResult with trending videos
        """
        max_results = min(kwargs.get("max_results", 5), 10)
        region_code = kwargs.get("region_code", "US").strip().upper()

        api_key = get_youtube_api_key()
        if not api_key:
            return TrendingVideosResult(
                success=False,
                count=0,
                message="YouTube API key is not configured. Please add GOOGLE_MAPS_API_KEY to your .env file."
            )

        try:
            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                "part": "snippet",
                "chart": "mostPopular",
                "regionCode": region_code,
                "maxResults": max_results,
                "key": api_key,
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return TrendingVideosResult(
                    success=False,
                    count=0,
                    message=f"YouTube API error: {data['error'].get('message', 'Unknown error')}"
                )

            videos = []
            for item in data.get("items", []):
                video_id = item["id"]
                snippet = item["snippet"]

                videos.append(YouTubeVideo(
                    video_id=video_id,
                    title=snippet["title"],
                    channel_name=snippet["channelTitle"],
                    description=snippet["description"][:200] + "..." if len(snippet["description"]) > 200 else snippet["description"],
                    published_at=snippet["publishedAt"],
                    thumbnail_url=snippet["thumbnails"]["medium"]["url"],
                    video_url=f"https://www.youtube.com/watch?v={video_id}"
                ))

            return TrendingVideosResult(
                success=True,
                videos=videos,
                count=len(videos),
                message=f"📈 Found {len(videos)} trending video(s) in {region_code}"
            )

        except Exception as e:
            return TrendingVideosResult(
                success=False,
                count=0,
                message=f"Failed to get trending videos: {str(e)}"
            )


class MyWatchHistoryResult(BaseModel):
    """Result of getting user's watch history."""
    success: bool
    videos: list[YouTubeVideo] = []
    count: int
    message: str


class GetMyWatchHistoryTool(Tool):
    """Tool for getting user's YouTube watch history (requires OAuth)."""

    @property
    def name(self) -> str:
        return "get_my_youtube_history"

    @property
    def description(self) -> str:
        return "get the user's personal YouTube watch history (recently watched videos)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of videos to return (default: 10, max: 25)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> MyWatchHistoryResult:
        """
        Get user's YouTube watch history.

        Args:
            max_results: Max results (default 10)

        Returns:
            MyWatchHistoryResult with watch history
        """
        max_results = min(kwargs.get("max_results", 10), 25)

        credentials = load_credentials()
        if not credentials:
            return MyWatchHistoryResult(
                success=False,
                count=0,
                message="YouTube OAuth is not connected. Please reconnect your Google account."
            )

        try:
            youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

            # Get watch history playlist (every user has a "History" playlist)
            # First get the user's channel to find the history playlist
            channels_response = youtube.channels().list(
                part="contentDetails",
                mine=True
            ).execute()

            if not channels_response.get("items"):
                return MyWatchHistoryResult(
                    success=False,
                    count=0,
                    message="Could not access YouTube account. Make sure YouTube OAuth is authorized."
                )

            # Note: YouTube removed direct watch history API access
            # Instead, get videos from "Liked Videos" or "Watch Later" as alternative
            request = youtube.playlistItems().list(
                part="snippet",
                myRating="like",
                maxResults=max_results
            )

            response = request.execute()

            videos = []
            for item in response.get("items", []):
                snippet = item["snippet"]
                video_id = snippet["resourceId"]["videoId"]

                videos.append(YouTubeVideo(
                    video_id=video_id,
                    title=snippet["title"],
                    channel_name=snippet["channelTitle"],
                    description=snippet["description"][:200] + "..." if len(snippet["description"]) > 200 else snippet["description"],
                    published_at=snippet["publishedAt"],
                    thumbnail_url=snippet["thumbnails"]["medium"]["url"] if "thumbnails" in snippet else None,
                    video_url=f"https://www.youtube.com/watch?v={video_id}"
                ))

            return MyWatchHistoryResult(
                success=True,
                videos=videos,
                count=len(videos),
                message=f"📺 Found {len(videos)} recently liked video(s) (Note: Full watch history access was removed by YouTube API)"
            )

        except Exception as e:
            return MyWatchHistoryResult(
                success=False,
                count=0,
                message=f"Failed to get watch history: {str(e)}"
            )


class MySubscriptionsResult(BaseModel):
    """Result of getting user's subscriptions."""
    success: bool
    channels: list[dict[str, Any]] = []
    count: int
    message: str


class GetMySubscriptionsTool(Tool):
    """Tool for getting user's YouTube subscriptions (requires OAuth)."""

    @property
    def name(self) -> str:
        return "get_my_youtube_subscriptions"

    @property
    def description(self) -> str:
        return "get the user's YouTube channel subscriptions"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of subscriptions to return (default: 10, max: 25)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> MySubscriptionsResult:
        """
        Get user's YouTube subscriptions.

        Args:
            max_results: Max results (default 10)

        Returns:
            MySubscriptionsResult with subscriptions
        """
        max_results = min(kwargs.get("max_results", 10), 25)

        credentials = load_credentials()
        if not credentials:
            return MySubscriptionsResult(
                success=False,
                count=0,
                message="YouTube OAuth is not connected. Please reconnect your Google account."
            )

        try:
            youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

            request = youtube.subscriptions().list(
                part="snippet",
                mine=True,
                maxResults=max_results
            )

            response = request.execute()

            channels = []
            for item in response.get("items", []):
                snippet = item["snippet"]
                channels.append({
                    "channel_id": snippet["resourceId"]["channelId"],
                    "channel_name": snippet["title"],
                    "description": snippet["description"][:150] + "..." if len(snippet["description"]) > 150 else snippet["description"],
                    "thumbnail": snippet["thumbnails"]["medium"]["url"] if "thumbnails" in snippet else None,
                })

            return MySubscriptionsResult(
                success=True,
                channels=channels,
                count=len(channels),
                message=f"📺 You're subscribed to {len(channels)} channel(s)"
            )

        except Exception as e:
            return MySubscriptionsResult(
                success=False,
                count=0,
                message=f"Failed to get subscriptions: {str(e)}"
            )


class MyPlaylistsResult(BaseModel):
    """Result of getting user's playlists."""
    success: bool
    playlists: list[dict[str, Any]] = []
    count: int
    message: str


class GetMyPlaylistsTool(Tool):
    """Tool for getting user's YouTube playlists (requires OAuth)."""

    @property
    def name(self) -> str:
        return "get_my_youtube_playlists"

    @property
    def description(self) -> str:
        return "get the user's YouTube playlists (including Watch Later, Liked Videos, etc.)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of playlists to return (default: 10, max: 25)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> MyPlaylistsResult:
        """
        Get user's YouTube playlists.

        Args:
            max_results: Max results (default 10)

        Returns:
            MyPlaylistsResult with playlists
        """
        max_results = min(kwargs.get("max_results", 10), 25)

        credentials = load_credentials()
        if not credentials:
            return MyPlaylistsResult(
                success=False,
                count=0,
                message="YouTube OAuth is not connected. Please reconnect your Google account."
            )

        try:
            youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

            request = youtube.playlists().list(
                part="snippet,contentDetails",
                mine=True,
                maxResults=max_results
            )

            response = request.execute()

            playlists = []
            for item in response.get("items", []):
                snippet = item["snippet"]
                content_details = item["contentDetails"]

                playlists.append({
                    "playlist_id": item["id"],
                    "title": snippet["title"],
                    "description": snippet.get("description", "")[:150],
                    "video_count": content_details["itemCount"],
                    "thumbnail": snippet["thumbnails"]["medium"]["url"] if "thumbnails" in snippet else None,
                })

            return MyPlaylistsResult(
                success=True,
                playlists=playlists,
                count=len(playlists),
                message=f"📝 You have {len(playlists)} playlist(s)"
            )

        except Exception as e:
            return MyPlaylistsResult(
                success=False,
                count=0,
                message=f"Failed to get playlists: {str(e)}"
            )
