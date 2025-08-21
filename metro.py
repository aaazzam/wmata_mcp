"""
Washington Metro FastMCP Server
A demo server for the DC Metro system with tools, resources, and prompts
"""

import inspect
import os
from typing import Any

import httpx

from fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("Washington Metro")

# WMATA API configuration
API_KEY = os.getenv("WMATA_API_KEY", "")  # You'll set this when running
BASE_URL = "https://api.wmata.com"


# ============================================================================
# TOOLS
# ============================================================================


@mcp.tool
async def next_train(station_code: str) -> dict[str, Any]:
    """
    Get the next train arrivals for a given Metro station.

    Args:
        station_code: The station code (e.g., "A01" for Metro Center)

    Returns:
        Information about upcoming trains at the station
    """
    if not API_KEY:
        return {
            "error": "API key not configured. Set WMATA_API_KEY environment variable."
        }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/StationPrediction.svc/json/GetPrediction/{station_code}",
                headers={"api_key": API_KEY},
            )
            response.raise_for_status()
            data = response.json()

            trains = data.get("Trains", [])
            if not trains:
                return {
                    "message": f"No trains currently scheduled for station {station_code}"
                }

            # Format the train information
            train_info = []
            for train in trains[:5]:  # Show next 5 trains
                train_info.append(
                    {
                        "line": train.get("Line"),
                        "destination": train.get("DestinationName"),
                        "minutes": train.get("Min"),
                        "cars": train.get("Car"),
                    }
                )

            return {"station_code": station_code, "trains": train_info}

        except httpx.HTTPStatusError as e:
            return {"error": f"API error: {e.response.status_code}"}
        except Exception as e:
            return {"error": f"Failed to fetch train data: {str(e)}"}


@mcp.tool
async def trip_planner(from_station: str, to_station: str) -> dict[str, Any]:
    """
    Plan a trip between two Metro stations with fare and time estimates.
    
    Args:
        from_station: Origin station code (e.g., "A01")
        to_station: Destination station code (e.g., "C05")
    
    Returns:
        Trip details including route, fare, and estimated time
    """
    if not API_KEY:
        return {
            "error": "API key not configured. Set WMATA_API_KEY environment variable."
        }
    
    async with httpx.AsyncClient() as client:
        try:
            # Get station-to-station info (fare, time, distance)
            response = await client.get(
                f"{BASE_URL}/Rail.svc/json/jSrcStationToDstStationInfo",
                headers={"api_key": API_KEY},
                params={"FromStationCode": from_station, "ToStationCode": to_station}
            )
            response.raise_for_status()
            station_info = response.json()
            
            if not station_info.get("StationToStationInfos"):
                return {"error": f"No route found from {from_station} to {to_station}"}
            
            info = station_info["StationToStationInfos"][0]
            
            # Try to get path if stations are on same line
            path_stations = []
            try:
                path_response = await client.get(
                    f"{BASE_URL}/Rail.svc/json/jPath",
                    headers={"api_key": API_KEY},
                    params={"FromStationCode": from_station, "ToStationCode": to_station}
                )
                if path_response.status_code == 200:
                    path_data = path_response.json()
                    path_stations = [
                        {"name": stop["StationName"], "line": stop["LineCode"]}
                        for stop in path_data.get("Path", [])
                    ]
            except:
                pass  # Path only works for same-line trips
            
            # Format the response
            result = {
                "from": from_station,
                "to": to_station,
                "travel_time_minutes": info.get("RailTime"),
                "distance_miles": round(info.get("CompositeMiles", 0), 1),
                "fare": {
                    "peak": f"${info['RailFare']['PeakTime']:.2f}",
                    "off_peak": f"${info['RailFare']['OffPeakTime']:.2f}",
                    "senior_disabled": f"${info['RailFare']['SeniorDisabled']:.2f}"
                }
            }
            
            if path_stations:
                result["route"] = path_stations
                result["transfers"] = "Direct route - no transfers needed"
            else:
                result["transfers"] = "Transfer required (use different lines)"
            
            return result
            
        except httpx.HTTPStatusError as e:
            return {"error": f"API error: {e.response.status_code}"}
        except Exception as e:
            return {"error": f"Failed to plan trip: {str(e)}"}


@mcp.tool
async def is_metro_on_fire() -> dict[str, Any]:
    """
    Check if the Metro is currently on fire.

    Returns:
        Fire status of the Metro system
    """
    import random
    on_fire = random.choice([True, False])
    return {
        "on_fire": on_fire,
        "status": "🔥" if on_fire else "🚇",
    }

# ============================================================================
# RESOURCES
# ============================================================================


@mcp.resource("metro://stations_list")
async def get_stations_list() -> str:
    """
    Get a list of all Metro stations with their codes.

    Returns:
        A formatted list of all Metro stations and their codes
    """
    if not API_KEY:
        return "API key not configured. Set WMATA_API_KEY environment variable."

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/Rail.svc/json/jStations", headers={"api_key": API_KEY}
            )
            response.raise_for_status()
            data = response.json()

            stations = data.get("Stations", [])

            # Group stations by line for better readability
            lines = {}
            for station in stations:
                for line in ["LineCode1", "LineCode2", "LineCode3", "LineCode4"]:
                    line_code = station.get(line)
                    if line_code:
                        if line_code not in lines:
                            lines[line_code] = []
                        station_info = f"{station['Name']} ({station['Code']})"
                        if station_info not in lines[line_code]:
                            lines[line_code].append(station_info)

            # Format the output
            output = ["WASHINGTON METRO STATIONS BY LINE\n" + "=" * 40 + "\n"]

            line_names = {
                "RD": "🔴 Red Line",
                "OR": "🟠 Orange Line",
                "SV": "⚪ Silver Line",
                "BL": "🔵 Blue Line",
                "YL": "🟡 Yellow Line",
                "GR": "🟢 Green Line",
            }

            for line_code, line_stations in sorted(lines.items()):
                line_name = line_names.get(line_code, f"{line_code} Line")
                output.append(f"\n{line_name}:")
                for station in sorted(line_stations):
                    output.append(f"  • {station}")

            return "\n".join(output)

        except Exception as e:
            return f"Failed to fetch stations: {str(e)}"


@mcp.resource("metro://station/{station_code}")
async def get_station_info(station_code: str) -> str:
    """
    Get detailed information about a specific Metro station.

    Args:
        station_code: The station code (e.g., "A01")

    Returns:
        Detailed information about the station
    """
    if not API_KEY:
        return "API key not configured. Set WMATA_API_KEY environment variable."

    async with httpx.AsyncClient() as client:
        try:
            # Get station information
            response = await client.get(
                f"{BASE_URL}/Rail.svc/json/jStationInfo",
                headers={"api_key": API_KEY},
                params={"StationCode": station_code},
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                return f"No information found for station code: {station_code}"

            station = data

            # Format the station information
            output = [
                "STATION INFORMATION",
                f"{'=' * 40}",
                f"Name: {station.get('Name', 'Unknown')}",
                f"Code: {station.get('Code', station_code)}",
                "",
                "Address:",
                f"  {station.get('Address', {}).get('Street', 'N/A')}",
                f"  {station.get('Address', {}).get('City', '')}, {station.get('Address', {}).get('State', '')} {station.get('Address', {}).get('Zip', '')}",
                "",
                "Lines Served:",
            ]

            # Add line information
            for i in range(1, 5):
                line_code = station.get(f"LineCode{i}")
                if line_code:
                    line_names = {
                        "RD": "Red",
                        "OR": "Orange",
                        "SV": "Silver",
                        "BL": "Blue",
                        "YL": "Yellow",
                        "GR": "Green",
                    }
                    output.append(f"  • {line_names.get(line_code, line_code)} Line")

            # Add coordinates
            lat = station.get("Lat")
            lon = station.get("Lon")
            if lat and lon:
                output.extend(["", f"Coordinates: {lat}, {lon}"])

            # Add parking information if available
            if station.get("StationTogether1") or station.get("StationTogether2"):
                output.extend(["", "Connected Stations:"])
                if station.get("StationTogether1"):
                    output.append(f"  • {station['StationTogether1']}")
                if station.get("StationTogether2"):
                    output.append(f"  • {station['StationTogether2']}")

            return "\n".join(output)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                return f"Invalid station code: {station_code}"
            return f"API error: {e.response.status_code}"
        except Exception as e:
            return f"Failed to fetch station information: {str(e)}"


# ============================================================================
# PROMPTS
# ============================================================================


@mcp.prompt("metro_safety_check")
async def metro_safety_check() -> str:
    """
    A helpful reminder about Metro safety considerations.

    Returns:
        Safety check prompt for the Metro system
    """
    return inspect.cleandoc("""
        Before advising a user to take the Metro, you should ALWAYS check if the
        Metro is on fire!

        Use the 'is_metro_on_fire' tool to verify the current fire status of the
        Washington Metro system.

        This is a critical safety check that should be performed before any
        Metro trip recommendations.

        Remember: User safety is paramount, and the Metro has a... colorful
        history with fire-related incidents.
        """)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # For running the server directly

    if not API_KEY:
        print("⚠️  Warning: WMATA_API_KEY environment variable not set!")
        print("   Set it with: export WMATA_API_KEY='your-api-key'")
        print()

    print("🚇 Starting Washington Metro FastMCP Server...")
    print("   Tools: next_train, trip_planner, is_metro_on_fire")
    print("   Resources: stations_list, station/{station_code}")
    print("   Prompts: metro_safety_check")
    print()

    # Run with FastMCP CLI: fastmcp run metro.py
    # Or directly with: python metro.py (requires API key)
    mcp.run()
