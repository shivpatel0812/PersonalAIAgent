"""Google Maps tools - allows the agent to use Google Maps APIs."""

from typing import Any
from pydantic import BaseModel
import os
import requests

from app.ai.tools.base import Tool, ToolParameter


def get_maps_api_key() -> str | None:
    """Get Google Maps API key from environment."""
    return os.getenv("GOOGLE_MAPS_API_KEY")


class DistanceTimeResult(BaseModel):
    """Result of calculating distance and time between locations."""
    success: bool
    origin: str
    destination: str
    distance_text: str | None = None
    distance_meters: int | None = None
    duration_text: str | None = None
    duration_seconds: int | None = None
    message: str


class GetDistanceTimeTool(Tool):
    """Tool for calculating distance and travel time between two locations."""

    @property
    def name(self) -> str:
        return "get_distance_time"

    @property
    def description(self) -> str:
        return "calculate distance and travel time between two locations (addresses or place names)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "origin",
                "type": "string",
                "description": "starting location (address or place name, e.g., 'New York, NY' or '1600 Amphitheatre Pkwy, Mountain View')",
                "required": True,
            },
            {
                "name": "destination",
                "type": "string",
                "description": "destination location (address or place name)",
                "required": True,
            },
            {
                "name": "mode",
                "type": "string",
                "description": "travel mode: 'driving' (default), 'walking', 'bicycling', or 'transit'",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> DistanceTimeResult:
        """
        Calculate distance and time between locations.

        Args:
            origin: Starting location
            destination: Destination location
            mode: Travel mode (default: driving)

        Returns:
            DistanceTimeResult with distance and time info
        """
        origin = kwargs.get("origin", "").strip()
        destination = kwargs.get("destination", "").strip()
        mode = kwargs.get("mode", "driving").strip().lower()

        if not origin:
            raise ValueError("Origin is required")
        if not destination:
            raise ValueError("Destination is required")

        api_key = get_maps_api_key()
        if not api_key:
            return DistanceTimeResult(
                success=False,
                origin=origin,
                destination=destination,
                message="Google Maps API key is not configured. Please add GOOGLE_MAPS_API_KEY to your .env file."
            )

        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": origin,
                "destinations": destination,
                "mode": mode,
                "key": api_key,
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data["status"] != "OK":
                return DistanceTimeResult(
                    success=False,
                    origin=origin,
                    destination=destination,
                    message=f"Maps API error: {data.get('error_message', data['status'])}"
                )

            element = data["rows"][0]["elements"][0]

            if element["status"] != "OK":
                return DistanceTimeResult(
                    success=False,
                    origin=origin,
                    destination=destination,
                    message=f"Could not calculate route: {element['status']}"
                )

            distance = element["distance"]
            duration = element["duration"]

            mode_emoji = {"driving": "🚗", "walking": "🚶", "bicycling": "🚴", "transit": "🚇"}
            emoji = mode_emoji.get(mode, "📍")

            message = f"{emoji} From '{origin}' to '{destination}' by {mode}:\n"
            message += f"Distance: {distance['text']}\n"
            message += f"Time: {duration['text']}"

            return DistanceTimeResult(
                success=True,
                origin=origin,
                destination=destination,
                distance_text=distance["text"],
                distance_meters=distance["value"],
                duration_text=duration["text"],
                duration_seconds=duration["value"],
                message=message
            )

        except Exception as e:
            return DistanceTimeResult(
                success=False,
                origin=origin,
                destination=destination,
                message=f"Failed to get distance/time: {str(e)}"
            )


class PlaceSearchResult(BaseModel):
    """Represents a place from search results."""
    name: str
    address: str
    place_id: str
    rating: float | None = None
    types: list[str] = []


class SearchPlacesResult(BaseModel):
    """Result of searching for places."""
    success: bool
    query: str
    places: list[PlaceSearchResult] = []
    count: int
    message: str


class SearchPlacesTool(Tool):
    """Tool for searching for places using Google Maps."""

    @property
    def name(self) -> str:
        return "search_places"

    @property
    def description(self) -> str:
        return "search for places, businesses, or points of interest on Google Maps"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "query",
                "type": "string",
                "description": "search query (e.g., 'pizza near me', 'coffee shops in San Francisco', 'Eiffel Tower')",
                "required": True,
            },
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of results (default: 5)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> SearchPlacesResult:
        """
        Search for places.

        Args:
            query: Search query
            max_results: Max results (default 5)

        Returns:
            SearchPlacesResult with matching places
        """
        query = kwargs.get("query", "").strip()
        max_results = kwargs.get("max_results", 5)

        if not query:
            raise ValueError("Search query is required")

        api_key = get_maps_api_key()
        if not api_key:
            return SearchPlacesResult(
                success=False,
                query=query,
                count=0,
                message="Google Maps API key is not configured. Please add GOOGLE_MAPS_API_KEY to your .env file."
            )

        try:
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                "query": query,
                "key": api_key,
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data["status"] not in ["OK", "ZERO_RESULTS"]:
                return SearchPlacesResult(
                    success=False,
                    query=query,
                    count=0,
                    message=f"Maps API error: {data.get('error_message', data['status'])}"
                )

            results = data.get("results", [])[:max_results]

            places = []
            for place in results:
                places.append(PlaceSearchResult(
                    name=place.get("name", "Unknown"),
                    address=place.get("formatted_address", "Address unavailable"),
                    place_id=place.get("place_id", ""),
                    rating=place.get("rating"),
                    types=place.get("types", [])
                ))

            return SearchPlacesResult(
                success=True,
                query=query,
                places=places,
                count=len(places),
                message=f"Found {len(places)} place(s) for '{query}'"
            )

        except Exception as e:
            return SearchPlacesResult(
                success=False,
                query=query,
                count=0,
                message=f"Failed to search places: {str(e)}"
            )


class GeocodeResult(BaseModel):
    """Result of geocoding an address."""
    success: bool
    address: str
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_id: str | None = None
    message: str


class GeocodeTool(Tool):
    """Tool for converting addresses to coordinates (geocoding)."""

    @property
    def name(self) -> str:
        return "geocode_address"

    @property
    def description(self) -> str:
        return "convert an address or place name to geographic coordinates (latitude/longitude)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "address",
                "type": "string",
                "description": "address or place name to geocode (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA')",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> GeocodeResult:
        """
        Geocode an address.

        Args:
            address: Address or place name

        Returns:
            GeocodeResult with coordinates
        """
        address = kwargs.get("address", "").strip()

        if not address:
            raise ValueError("Address is required")

        api_key = get_maps_api_key()
        if not api_key:
            return GeocodeResult(
                success=False,
                address=address,
                message="Google Maps API key is not configured. Please add GOOGLE_MAPS_API_KEY to your .env file."
            )

        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": address,
                "key": api_key,
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data["status"] != "OK":
                return GeocodeResult(
                    success=False,
                    address=address,
                    message=f"Could not geocode address: {data['status']}"
                )

            result = data["results"][0]
            location = result["geometry"]["location"]

            return GeocodeResult(
                success=True,
                address=address,
                formatted_address=result["formatted_address"],
                latitude=location["lat"],
                longitude=location["lng"],
                place_id=result.get("place_id"),
                message=f"📍 {result['formatted_address']}\nCoordinates: {location['lat']}, {location['lng']}"
            )

        except Exception as e:
            return GeocodeResult(
                success=False,
                address=address,
                message=f"Failed to geocode: {str(e)}"
            )
