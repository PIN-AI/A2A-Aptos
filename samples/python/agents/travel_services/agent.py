import json
import logging
import random
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from task_manager import AgentWithTaskManager
# Import Aptos related libraries
from common.aptos_config import AptosConfig
from common.aptos_blockchain import AptosTaskManager
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configure logger
logger = logging.getLogger(__name__)

# Global reference to the current agent instance for tool functions
_current_agent_instance = None

# Local cache of created booking_ids for demo purposes
booking_ids = set()

# Global destinations database with worldwide coverage
DESTINATIONS = {
    "asia": [
        {"name": "Tokyo", "country": "Japan", "type": "City", "season": "Spring/Fall", "budget": "$$$", "highlights": ["Cherry Blossoms", "Temples", "Modern Culture"]},
        {"name": "Bangkok", "country": "Thailand", "type": "City", "season": "Cool/Dry", "budget": "$$", "highlights": ["Temples", "Street Food", "Markets"]},
        {"name": "Singapore", "country": "Singapore", "type": "City", "season": "Year-round", "budget": "$$$", "highlights": ["Gardens", "Food Scene", "Architecture"]},
        {"name": "Seoul", "country": "South Korea", "type": "City", "season": "Spring/Fall", "budget": "$$", "highlights": ["K-Culture", "Palaces", "Technology"]},
        {"name": "Bali", "country": "Indonesia", "type": "Island", "season": "Dry", "budget": "$$", "highlights": ["Beaches", "Temples", "Rice Terraces"]},
        {"name": "Hong Kong", "country": "China", "type": "City", "season": "Fall/Winter", "budget": "$$$", "highlights": ["Skyline", "Dim Sum", "Shopping"]},
        {"name": "Kyoto", "country": "Japan", "type": "Historic City", "season": "Spring/Fall", "budget": "$$", "highlights": ["Traditional Culture", "Temples", "Gardens"]},
        {"name": "Mumbai", "country": "India", "type": "City", "season": "Winter", "budget": "$", "highlights": ["Bollywood", "Street Food", "Architecture"]}
    ],
    "europe": [
        {"name": "Paris", "country": "France", "type": "City", "season": "Spring/Fall", "budget": "$$$", "highlights": ["Art", "Architecture", "Cuisine"]},
        {"name": "Rome", "country": "Italy", "type": "Historic City", "season": "Spring/Fall", "budget": "$$", "highlights": ["Ancient History", "Art", "Food"]},
        {"name": "London", "country": "UK", "type": "City", "season": "Summer", "budget": "$$$", "highlights": ["Museums", "History", "Culture"]},
        {"name": "Barcelona", "country": "Spain", "type": "City", "season": "Spring/Fall", "budget": "$$", "highlights": ["Architecture", "Beaches", "Food"]},
        {"name": "Amsterdam", "country": "Netherlands", "type": "City", "season": "Spring/Summer", "budget": "$$", "highlights": ["Canals", "Museums", "Culture"]},
        {"name": "Santorini", "country": "Greece", "type": "Island", "season": "Summer", "budget": "$$$", "highlights": ["Sunsets", "Beaches", "Architecture"]},
        {"name": "Prague", "country": "Czech Republic", "type": "Historic City", "season": "Spring/Fall", "budget": "$", "highlights": ["Architecture", "History", "Beer"]},
        {"name": "Vienna", "country": "Austria", "type": "City", "season": "Spring/Fall", "budget": "$$", "highlights": ["Music", "Architecture", "Coffee Culture"]}
    ],
    "americas": [
        {"name": "New York", "country": "USA", "type": "City", "season": "Spring/Fall", "budget": "$$$", "highlights": ["Broadway", "Museums", "Food Scene"]},
        {"name": "San Francisco", "country": "USA", "type": "City", "season": "Year-round", "budget": "$$$", "highlights": ["Golden Gate", "Tech Culture", "Food"]},
        {"name": "Rio de Janeiro", "country": "Brazil", "type": "City", "season": "Summer", "budget": "$$", "highlights": ["Beaches", "Carnival", "Christ Statue"]},
        {"name": "Buenos Aires", "country": "Argentina", "type": "City", "season": "Spring/Fall", "budget": "$", "highlights": ["Tango", "Steakhouses", "Architecture"]},
        {"name": "Vancouver", "country": "Canada", "type": "City", "season": "Summer", "budget": "$$", "highlights": ["Nature", "Multiculturalism", "Outdoor Activities"]},
        {"name": "Mexico City", "country": "Mexico", "type": "City", "season": "Year-round", "budget": "$", "highlights": ["Culture", "Food", "History"]},
        {"name": "Toronto", "country": "Canada", "type": "City", "season": "Summer", "budget": "$$", "highlights": ["Diversity", "CN Tower", "Food Scene"]},
        {"name": "Los Angeles", "country": "USA", "type": "City", "season": "Year-round", "budget": "$$$", "highlights": ["Hollywood", "Beaches", "Weather"]}
    ],
    "oceania": [
        {"name": "Sydney", "country": "Australia", "type": "City", "season": "Spring/Fall", "budget": "$$$", "highlights": ["Opera House", "Harbor", "Beaches"]},
        {"name": "Melbourne", "country": "Australia", "type": "City", "season": "Spring/Fall", "budget": "$$", "highlights": ["Coffee Culture", "Arts", "Food Scene"]},
        {"name": "Auckland", "country": "New Zealand", "type": "City", "season": "Summer", "budget": "$$", "highlights": ["Nature", "Adventure Sports", "Wine"]},
        {"name": "Queenstown", "country": "New Zealand", "type": "Adventure", "season": "Summer", "budget": "$$$", "highlights": ["Adventure Sports", "Scenery", "Wine"]}
    ],
    "africa": [
        {"name": "Cape Town", "country": "South Africa", "type": "City", "season": "Summer", "budget": "$$", "highlights": ["Table Mountain", "Wine", "Beaches"]},
        {"name": "Marrakech", "country": "Morocco", "type": "Historic City", "season": "Spring/Fall", "budget": "$", "highlights": ["Medina", "Culture", "Markets"]},
        {"name": "Cairo", "country": "Egypt", "type": "Historic City", "season": "Winter", "budget": "$", "highlights": ["Pyramids", "History", "Nile River"]}
    ]
}

# Hotels database with global coverage
HOTELS = {
    "luxury": [
        {"name": "The Ritz-Carlton", "location": "Global", "type": "Luxury Chain", "price_range": "$$$$$", "amenities": ["Spa", "Fine Dining", "Concierge"]},
        {"name": "Four Seasons", "location": "Global", "type": "Luxury Chain", "price_range": "$$$$$", "amenities": ["Spa", "Pool", "Business Center"]},
        {"name": "Mandarin Oriental", "location": "Asia/Europe", "type": "Luxury Chain", "price_range": "$$$$$", "amenities": ["Spa", "Fine Dining", "Cultural Programs"]},
        {"name": "Park Hyatt", "location": "Global", "type": "Luxury Chain", "price_range": "$$$$", "amenities": ["Design", "Spa", "Fine Dining"]},
        {"name": "St. Regis", "location": "Global", "type": "Luxury Chain", "price_range": "$$$$$", "amenities": ["Butler Service", "Spa", "Fine Dining"]}
    ],
    "business": [
        {"name": "Marriott", "location": "Global", "type": "Business Chain", "price_range": "$$$", "amenities": ["Business Center", "Fitness", "Meeting Rooms"]},
        {"name": "Hilton", "location": "Global", "type": "Business Chain", "price_range": "$$$", "amenities": ["Business Center", "Pool", "Fitness"]},
        {"name": "Hyatt", "location": "Global", "type": "Business Chain", "price_range": "$$$", "amenities": ["Business Center", "Fitness", "Restaurant"]},
        {"name": "Sheraton", "location": "Global", "type": "Business Chain", "price_range": "$$$", "amenities": ["Business Center", "Pool", "Club Lounge"]},
        {"name": "InterContinental", "location": "Global", "type": "Business Chain", "price_range": "$$$", "amenities": ["Business Center", "Spa", "Fine Dining"]}
    ],
    "budget": [
        {"name": "Holiday Inn Express", "location": "Global", "type": "Budget Chain", "price_range": "$$", "amenities": ["Free Breakfast", "Fitness", "WiFi"]},
        {"name": "Hampton Inn", "location": "North America", "type": "Budget Chain", "price_range": "$$", "amenities": ["Free Breakfast", "Pool", "Fitness"]},
        {"name": "Ibis", "location": "Europe/Asia", "type": "Budget Chain", "price_range": "$$", "amenities": ["WiFi", "Restaurant", "24/7 Reception"]},
        {"name": "Best Western", "location": "Global", "type": "Budget Chain", "price_range": "$$", "amenities": ["WiFi", "Breakfast", "Fitness"]},
        {"name": "Travelodge", "location": "UK/Europe", "type": "Budget Chain", "price_range": "$", "amenities": ["WiFi", "Basic Amenities", "Central Location"]}
    ],
    "boutique": [
        {"name": "Local Boutique Hotels", "location": "Varies", "type": "Boutique", "price_range": "$$$", "amenities": ["Unique Design", "Local Experience", "Personalized Service"]},
        {"name": "Boutique Design Hotels", "location": "Major Cities", "type": "Design", "price_range": "$$$", "amenities": ["Architecture", "Art", "Local Culture"]},
        {"name": "Historic Hotels", "location": "Heritage Sites", "type": "Historic", "price_range": "$$$", "amenities": ["History", "Character", "Local Stories"]}
    ]
}

# Airlines and airports database
AIRLINES = {
    "major_international": [
        {"name": "Emirates", "region": "Middle East", "hub": "Dubai (DXB)", "class_options": ["Economy", "Business", "First"]},
        {"name": "Singapore Airlines", "region": "Asia", "hub": "Singapore (SIN)", "class_options": ["Economy", "Premium Economy", "Business", "Suites"]},
        {"name": "Qatar Airways", "region": "Middle East", "hub": "Doha (DOH)", "class_options": ["Economy", "Business", "First"]},
        {"name": "Lufthansa", "region": "Europe", "hub": "Frankfurt (FRA), Munich (MUC)", "class_options": ["Economy", "Premium Economy", "Business", "First"]},
        {"name": "British Airways", "region": "Europe", "hub": "London Heathrow (LHR)", "class_options": ["Economy", "Premium Economy", "Business", "First"]},
        {"name": "United Airlines", "region": "North America", "hub": "Multiple US Cities", "class_options": ["Economy", "Premium Economy", "Business", "First"]},
        {"name": "American Airlines", "region": "North America", "hub": "Multiple US Cities", "class_options": ["Economy", "Premium Economy", "Business", "First"]},
        {"name": "Air France", "region": "Europe", "hub": "Paris (CDG)", "class_options": ["Economy", "Premium Economy", "Business", "La Première"]}
    ],
    "low_cost": [
        {"name": "Ryanair", "region": "Europe", "focus": "Budget European Travel", "class_options": ["Economy"]},
        {"name": "EasyJet", "region": "Europe", "focus": "Budget European Travel", "class_options": ["Economy"]},
        {"name": "Southwest", "region": "North America", "focus": "Budget US Domestic", "class_options": ["Economy"]},
        {"name": "JetBlue", "region": "North America", "focus": "US Domestic + Caribbean", "class_options": ["Economy", "Mint"]},
        {"name": "AirAsia", "region": "Asia", "focus": "Budget Asian Travel", "class_options": ["Economy"]}
    ]
}

# Weather and seasonal information
SEASONAL_INFO = {
    "spring": {"months": [3, 4, 5], "description": "Mild weather, blooming flowers, moderate crowds"},
    "summer": {"months": [6, 7, 8], "description": "Warm weather, peak tourist season, higher prices"},
    "fall": {"months": [9, 10, 11], "description": "Cooler weather, changing leaves, shoulder season"},
    "winter": {"months": [12, 1, 2], "description": "Cold weather, fewer crowds, lower prices"}
}

# Local attractions database
ATTRACTIONS = {
    "museums": ["Art Museums", "History Museums", "Science Museums", "Local Culture Centers"],
    "landmarks": ["Historic Sites", "Architectural Wonders", "Religious Sites", "Natural Landmarks"],
    "entertainment": ["Theaters", "Music Venues", "Nightlife", "Sports Events"],
    "outdoor": ["Parks", "Gardens", "Beaches", "Hiking Trails"],
    "shopping": ["Markets", "Malls", "Local Crafts", "Fashion Districts"],
    "food": ["Local Restaurants", "Street Food", "Food Markets", "Cooking Classes"]
}

def search_destinations(
    region: Optional[str] = None,
    budget: Optional[str] = None,
    season: Optional[str] = None,
    travel_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search for travel destinations based on preferences.
    
    Args:
        region (str, optional): Geographic region (asia, europe, americas, oceania, africa)
        budget (str, optional): Budget range ($, $$, $$$, $$$$, $$$$$)
        season (str, optional): Best travel season (spring, summer, fall, winter)
        travel_type (str, optional): Type of destination (city, island, historic, adventure)
        
    Returns:
        List[Dict[str, Any]]: List of matching destinations
    """
    results = []
    
    # If region is specified, search only that region
    if region and region.lower() in DESTINATIONS:
        search_regions = [region.lower()]
    else:
        # Search all regions
        search_regions = DESTINATIONS.keys()
    
    for region_name in search_regions:
        for destination in DESTINATIONS[region_name]:
            match = True
            
            # Filter by budget if provided
            if budget and budget != destination["budget"]:
                match = False
                
            # Filter by season if provided
            if season and season.lower() not in destination["season"].lower():
                match = False
                
            # Filter by type if provided
            if travel_type and travel_type.lower() not in destination["type"].lower():
                match = False
                
            if match:
                # Add region info to result
                result_destination = destination.copy()
                result_destination["region"] = region_name
                results.append(result_destination)
    
    # Sort by budget (lower cost first) then by name
    budget_order = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4, "$$$$$": 5}
    results.sort(key=lambda x: (budget_order.get(x["budget"], 3), x["name"]))
    return results[:15]  # Limit to top 15 results


def search_hotels(
    city: Optional[str] = None,
    hotel_type: Optional[str] = None,
    budget: Optional[str] = None,
    amenities: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search for hotels based on location and preferences.
    
    Args:
        city (str, optional): Target city or destination
        hotel_type (str, optional): Hotel category (luxury, business, budget, boutique)
        budget (str, optional): Budget range ($, $$, $$$, $$$$, $$$$$)
        amenities (str, optional): Desired amenities (spa, pool, fitness, etc.)
        
    Returns:
        List[Dict[str, Any]]: List of matching hotels
    """
    results = []
    
    # If hotel_type is specified, search only that category
    if hotel_type and hotel_type.lower() in HOTELS:
        search_categories = [hotel_type.lower()]
    else:
        # Search all categories
        search_categories = HOTELS.keys()
    
    for category in search_categories:
        for hotel in HOTELS[category]:
            match = True
            
            # Filter by location if provided
            if city and city.lower() not in hotel["location"].lower() and hotel["location"] != "Global":
                match = False
                
            # Filter by budget if provided
            if budget and budget != hotel["price_range"]:
                match = False
                
            # Filter by amenities if provided
            if amenities:
                amenity_keywords = amenities.lower().split()
                hotel_amenities = " ".join(hotel["amenities"]).lower()
                if not any(keyword in hotel_amenities for keyword in amenity_keywords):
                    match = False
                    
            if match:
                # Add category info to result
                result_hotel = hotel.copy()
                result_hotel["category"] = category
                results.append(result_hotel)
    
    return results


def search_flights(
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    departure_date: Optional[str] = None,
    travel_class: Optional[str] = None,
    airline_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search for flight options based on route and preferences.
    
    Args:
        origin (str, optional): Departure city or airport
        destination (str, optional): Destination city or airport
        departure_date (str, optional): Departure date (YYYY-MM-DD)
        travel_class (str, optional): Class of service (economy, business, first)
        airline_type (str, optional): Airline category (major_international, low_cost)
        
    Returns:
        List[Dict[str, Any]]: List of matching airlines and flight options
    """
    results = []
    
    # If airline_type is specified, search only that category
    if airline_type and airline_type in AIRLINES:
        search_categories = [airline_type]
    else:
        # Search all categories
        search_categories = AIRLINES.keys()
    
    for category in search_categories:
        for airline in AIRLINES[category]:
            match = True
            
            # Filter by travel class if provided
            if travel_class:
                class_available = any(travel_class.lower() in class_option.lower() 
                                    for class_option in airline["class_options"])
                if not class_available:
                    match = False
            
            # Basic route matching (simplified for demo)
            if origin or destination:
                # For demo purposes, assume all airlines can serve major routes
                # In real implementation, this would check actual route networks
                pass
                    
            if match:
                # Add category info to result
                result_airline = airline.copy()
                result_airline["category"] = category
                
                # Add estimated flight info for demo
                if origin and destination:
                    result_airline["route"] = f"{origin} -> {destination}"
                    if departure_date:
                        result_airline["departure_date"] = departure_date
                    result_airline["estimated_duration"] = "8-15 hours (varies by route)"
                    result_airline["price_estimate"] = "$500-$3000 (varies by class and route)"
                
                results.append(result_airline)
    
    return results


def get_weather_info(
    destination: Optional[str] = None,
    travel_month: Optional[int] = None
) -> Dict[str, Any]:
    """Get weather information for a destination and time period.
    
    Args:
        destination (str, optional): Target destination
        travel_month (int, optional): Month of travel (1-12)
        
    Returns:
        Dict[str, Any]: Weather information and recommendations
    """
    if not destination:
        return {
            "error": "Destination is required for weather information",
            "seasonal_tips": SEASONAL_INFO
        }
    
    # Determine season based on travel month
    current_season = "year-round"
    if travel_month:
        for season, info in SEASONAL_INFO.items():
            if travel_month in info["months"]:
                current_season = season
                break
    
    # Find destination in database for specific recommendations
    destination_info = None
    for region in DESTINATIONS.values():
        for dest in region:
            if destination.lower() in dest["name"].lower():
                destination_info = dest
                break
        if destination_info:
            break
    
    weather_info = {
        "destination": destination,
        "travel_month": travel_month,
        "current_season": current_season,
        "seasonal_description": SEASONAL_INFO.get(current_season, {}).get("description", ""),
        "general_recommendations": [
            "Check local weather forecasts before departure",
            "Pack appropriate clothing for the season",
            "Consider travel insurance for weather-related delays"
        ]
    }
    
    if destination_info:
        weather_info["best_season_for_destination"] = destination_info["season"]
        weather_info["destination_specific_tips"] = [
            f"Best time to visit {destination}: {destination_info['season']}",
            f"Budget level: {destination_info['budget']}",
            f"Highlights: {', '.join(destination_info['highlights'])}"
        ]
    
    return weather_info


def get_local_attractions(
    destination: Optional[str] = None,
    attraction_type: Optional[str] = None
) -> Dict[str, Any]:
    """Get local attractions and activities for a destination.
    
    Args:
        destination (str, optional): Target destination
        attraction_type (str, optional): Type of attraction (museums, landmarks, entertainment, etc.)
        
    Returns:
        Dict[str, Any]: Local attractions and activity recommendations
    """
    if not destination:
        return {
            "error": "Destination is required for attraction information",
            "available_types": list(ATTRACTIONS.keys()),
            "general_categories": ATTRACTIONS
        }
    
    # Find destination-specific highlights
    destination_highlights = []
    for region in DESTINATIONS.values():
        for dest in region:
            if destination.lower() in dest["name"].lower():
                destination_highlights = dest["highlights"]
                break
        if destination_highlights:
            break
    
    attractions_info = {
        "destination": destination,
        "destination_highlights": destination_highlights,
        "attraction_categories": {}
    }
    
    # If specific attraction type is requested
    if attraction_type and attraction_type.lower() in ATTRACTIONS:
        attractions_info["requested_type"] = attraction_type
        attractions_info["specific_attractions"] = ATTRACTIONS[attraction_type.lower()]
    else:
        # Provide all attraction types
        for category, attractions in ATTRACTIONS.items():
            attractions_info["attraction_categories"][category] = attractions
    
    # Add general recommendations
    attractions_info["recommendations"] = [
        "Book popular attractions in advance",
        "Check opening hours and seasonal closures",
        "Consider guided tours for historical sites",
        "Try local food experiences",
        "Respect local customs and dress codes"
    ]
    
    return attractions_info

def book_hotel(
    hotel_name: str,
    city: str,
    checkin_date: str,
    checkout_date: str,
    guests: str,
    room_type: Optional[str] = None,
    special_requests: Optional[str] = None,
    tool_context: ToolContext = None
) -> Dict[str, Any]:
    """Book a hotel reservation with blockchain verification.
    
    Args:
        hotel_name (str): Name of the hotel
        city (str): City where the hotel is located
        checkin_date (str): Check-in date (YYYY-MM-DD)
        checkout_date (str): Check-out date (YYYY-MM-DD)
        guests (str): Number of guests
        room_type (str, optional): Type of room requested
        special_requests (str, optional): Special requests or preferences
        tool_context (ToolContext): Context for blockchain operations
        
    Returns:
        Dict[str, Any]: Hotel booking confirmation with blockchain completion
    """
    try:
        # Generate booking ID
        booking_id = 'HTL_' + str(random.randint(1000000, 9999999))
        booking_ids.add(booking_id)
        
        # Calculate estimated cost (demo purposes)
        import random
        base_cost = random.randint(150, 800)  # $150-800 per night
        nights = 1  # Simplified calculation
        total_cost = base_cost * nights
        
        # Create booking response
        booking_response = {
            "booking_id": booking_id,
            "booking_type": "hotel",
            "status": "confirmed",
            "hotel_name": hotel_name,
            "city": city,
            "checkin_date": checkin_date,
            "checkout_date": checkout_date,
            "guests": guests,
            "room_type": room_type or "Standard Room",
            "special_requests": special_requests or "None",
            "estimated_cost": f"${total_cost}",
            "currency": "USD",
            "confirmation_number": f"CONF-{booking_id}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Complete task on blockchain
        blockchain_result = _complete_task_on_blockchain(tool_context)
        if blockchain_result:
            booking_response['blockchain_completion'] = blockchain_result
            logger.info(f"[APTOS NETWORK] Hotel booking {booking_id} completed on blockchain")
        
        return booking_response
        
    except Exception as e:
        logger.error(f"Error processing hotel booking: {e}")
        return {
            "error": f"Hotel booking failed: {str(e)}",
            "booking_id": None,
            "status": "failed"
        }


def book_flight(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: str = "1",
    travel_class: Optional[str] = None,
    airline_preference: Optional[str] = None,
    tool_context: ToolContext = None
) -> Dict[str, Any]:
    """Book a flight with blockchain verification.
    
    Args:
        origin (str): Departure city or airport
        destination (str): Destination city or airport
        departure_date (str): Departure date (YYYY-MM-DD)
        return_date (str, optional): Return date for round trip (YYYY-MM-DD)
        passengers (str): Number of passengers
        travel_class (str, optional): Class of service (economy, business, first)
        airline_preference (str, optional): Preferred airline
        tool_context (ToolContext): Context for blockchain operations
        
    Returns:
        Dict[str, Any]: Flight booking confirmation with blockchain completion
    """
    try:
        # Generate booking ID
        booking_id = 'FLT_' + str(random.randint(1000000, 9999999))
        booking_ids.add(booking_id)
        
        # Select airline (demo purposes)
        selected_airline = airline_preference or "United Airlines"
        
        # Calculate estimated cost (demo purposes)
        import random
        base_cost = random.randint(400, 3000)  # $400-3000 depending on route and class
        passenger_count = int(passengers) if passengers.isdigit() else 1
        total_cost = base_cost * passenger_count
        
        # Determine trip type
        trip_type = "round-trip" if return_date else "one-way"
        
        # Create booking response
        booking_response = {
            "booking_id": booking_id,
            "booking_type": "flight",
            "status": "confirmed",
            "airline": selected_airline,
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "trip_type": trip_type,
            "passengers": passengers,
            "travel_class": travel_class or "Economy",
            "estimated_cost": f"${total_cost}",
            "currency": "USD",
            "confirmation_number": f"CONF-{booking_id}",
            "flight_details": {
                "outbound": f"{origin} -> {destination} on {departure_date}",
                "return": f"{destination} -> {origin} on {return_date}" if return_date else None
            },
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Complete task on blockchain
        blockchain_result = _complete_task_on_blockchain(tool_context)
        if blockchain_result:
            booking_response['blockchain_completion'] = blockchain_result
            logger.info(f"[APTOS NETWORK] Flight booking {booking_id} completed on blockchain")
        
        return booking_response
        
    except Exception as e:
        logger.error(f"Error processing flight booking: {e}")
        return {
            "error": f"Flight booking failed: {str(e)}",
            "booking_id": None,
            "status": "failed"
        }


def create_comprehensive_itinerary(
    destination: str,
    start_date: str,
    end_date: str,
    budget: str,
    travel_style: Optional[str] = None,
    interests: Optional[str] = None,
    special_requirements: Optional[str] = None,
    tool_context: ToolContext = None
) -> Dict[str, Any]:
    """Create a comprehensive travel itinerary with blockchain verification.
    
    Args:
        destination (str): Main travel destination
        start_date (str): Trip start date (YYYY-MM-DD)
        end_date (str): Trip end date (YYYY-MM-DD)
        budget (str): Budget level ($, $$, $$$, $$$$, $$$$$)
        travel_style (str, optional): Style of travel (luxury, adventure, cultural, relaxed)
        interests (str, optional): Traveler interests (food, history, nature, nightlife, etc.)
        special_requirements (str, optional): Special needs or requirements
        tool_context (ToolContext): Context for blockchain operations
        
    Returns:
        Dict[str, Any]: Comprehensive itinerary with blockchain completion
    """
    try:
        # Generate itinerary ID
        itinerary_id = 'ITN_' + str(random.randint(1000000, 9999999))
        
        # Calculate trip duration
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        duration = (end - start).days
        
        # Find destination info
        destination_info = None
        for region in DESTINATIONS.values():
            for dest in region:
                if destination.lower() in dest["name"].lower():
                    destination_info = dest
                    break
            if destination_info:
                break
        
        # Create day-by-day itinerary (simplified)
        daily_activities = []
        for day_num in range(1, min(duration + 1, 8)):  # Limit to 7 days for demo
            day_activities = {
                f"day_{day_num}": {
                    "date": (start + timedelta(days=day_num-1)).strftime("%Y-%m-%d"),
                    "morning": "Breakfast and local sightseeing",
                    "afternoon": "Main attraction visit or activity",
                    "evening": "Dinner and local culture experience"
                }
            }
            daily_activities.append(day_activities)
        
        # Estimate total cost
        import random
        budget_ranges = {"$": (500, 1000), "$$": (1000, 2500), "$$$": (2500, 5000), 
                        "$$$$": (5000, 8000), "$$$$$": (8000, 15000)}
        cost_range = budget_ranges.get(budget, (1000, 3000))
        estimated_cost = random.randint(cost_range[0], cost_range[1])
        
        # Create comprehensive itinerary response
        itinerary_response = {
            "itinerary_id": itinerary_id,
            "booking_type": "comprehensive_itinerary",
            "status": "confirmed",
            "destination": destination,
            "start_date": start_date,
            "end_date": end_date,
            "duration_days": duration,
            "budget_level": budget,
            "travel_style": travel_style or "balanced",
            "interests": interests or "general sightseeing",
            "special_requirements": special_requirements or "None",
            "estimated_total_cost": f"${estimated_cost}",
            "currency": "USD",
            "daily_activities": daily_activities,
            "included_services": [
                "Accommodation recommendations",
                "Transportation guidance", 
                "Activity suggestions",
                "Restaurant recommendations",
                "Local tips and cultural insights"
            ],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add destination-specific information if found
        if destination_info:
            itinerary_response["destination_highlights"] = destination_info["highlights"]
            itinerary_response["best_season"] = destination_info["season"]
            itinerary_response["destination_type"] = destination_info["type"]
        
        # Complete task on blockchain
        blockchain_result = _complete_task_on_blockchain(tool_context)
        if blockchain_result:
            itinerary_response['blockchain_completion'] = blockchain_result
            logger.info(f"[APTOS NETWORK] Comprehensive itinerary {itinerary_id} completed on blockchain")
        
        return itinerary_response
        
    except Exception as e:
        logger.error(f"Error creating comprehensive itinerary: {e}")
        return {
            "error": f"Itinerary creation failed: {str(e)}",
            "itinerary_id": None,
            "status": "failed"
        }

def create_hotel_booking_form(
    hotel_name: Optional[str] = None,
    city: Optional[str] = None,
    checkin_date: Optional[str] = None,
    checkout_date: Optional[str] = None,
    guests: Optional[str] = None,
    room_type: Optional[str] = None,
    special_requests: Optional[str] = None
) -> Dict[str, Any]:
    """Create a hotel booking form for the user to fill out.
    
    Args:
        hotel_name (str, optional): Hotel name
        city (str, optional): City where the hotel is located
        checkin_date (str, optional): Check-in date (YYYY-MM-DD)
        checkout_date (str, optional): Check-out date (YYYY-MM-DD)
        guests (str, optional): Number of guests
        room_type (str, optional): Type of room requested
        special_requests (str, optional): Special requests
        
    Returns:
        Dict[str, Any]: A dictionary containing the hotel booking form data
    """
    booking_id = 'HTL_FORM_' + str(random.randint(1000000, 9999999))
    
    # Set default check-in date to tomorrow if not provided
    if not checkin_date:
        tomorrow = datetime.now() + timedelta(days=1)
        checkin_date = tomorrow.strftime("%Y-%m-%d")
    
    # Set default check-out date to day after check-in if not provided
    if not checkout_date:
        if checkin_date:
            checkin = datetime.strptime(checkin_date, "%Y-%m-%d")
            checkout = checkin + timedelta(days=1)
            checkout_date = checkout.strftime("%Y-%m-%d")
        else:
            checkout_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    return {
        'form_id': booking_id,
        'form_type': 'hotel_booking',
        'hotel_name': hotel_name or '<hotel name>',
        'city': city or '<city>',
        'checkin_date': checkin_date,
        'checkout_date': checkout_date,
        'guests': guests or '1',
        'room_type': room_type or 'Standard Room',
        'special_requests': special_requests or 'None',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def create_flight_booking_form(
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    departure_date: Optional[str] = None,
    return_date: Optional[str] = None,
    passengers: Optional[str] = None,
    travel_class: Optional[str] = None,
    airline_preference: Optional[str] = None
) -> Dict[str, Any]:
    """Create a flight booking form for the user to fill out.
    
    Args:
        origin (str, optional): Departure city or airport
        destination (str, optional): Destination city or airport
        departure_date (str, optional): Departure date (YYYY-MM-DD)
        return_date (str, optional): Return date (YYYY-MM-DD)
        passengers (str, optional): Number of passengers
        travel_class (str, optional): Class of service
        airline_preference (str, optional): Preferred airline
        
    Returns:
        Dict[str, Any]: A dictionary containing the flight booking form data
    """
    booking_id = 'FLT_FORM_' + str(random.randint(1000000, 9999999))
    
    # Set default departure date to next week if not provided
    if not departure_date:
        next_week = datetime.now() + timedelta(days=7)
        departure_date = next_week.strftime("%Y-%m-%d")
    
    return {
        'form_id': booking_id,
        'form_type': 'flight_booking',
        'origin': origin or '<departure city>',
        'destination': destination or '<destination city>',
        'departure_date': departure_date,
        'return_date': return_date or '',
        'passengers': passengers or '1',
        'travel_class': travel_class or 'Economy',
        'airline_preference': airline_preference or 'No preference',
        'trip_type': 'round-trip' if return_date else 'one-way',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def create_itinerary_form(
    destination: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    budget: Optional[str] = None,
    travel_style: Optional[str] = None,
    interests: Optional[str] = None,
    special_requirements: Optional[str] = None
) -> Dict[str, Any]:
    """Create a comprehensive itinerary planning form.
    
    Args:
        destination (str, optional): Main travel destination
        start_date (str, optional): Trip start date (YYYY-MM-DD)
        end_date (str, optional): Trip end date (YYYY-MM-DD)
        budget (str, optional): Budget level
        travel_style (str, optional): Style of travel
        interests (str, optional): Traveler interests
        special_requirements (str, optional): Special needs
        
    Returns:
        Dict[str, Any]: A dictionary containing the itinerary form data
    """
    form_id = 'ITN_FORM_' + str(random.randint(1000000, 9999999))
    
    # Set default dates if not provided (next month for 7 days)
    if not start_date:
        next_month = datetime.now() + timedelta(days=30)
        start_date = next_month.strftime("%Y-%m-%d")
    
    if not end_date:
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = start + timedelta(days=7)  # Default 7-day trip
            end_date = end.strftime("%Y-%m-%d")
        else:
            end_date = (datetime.now() + timedelta(days=37)).strftime("%Y-%m-%d")
    
    return {
        'form_id': form_id,
        'form_type': 'comprehensive_itinerary',
        'destination': destination or '<destination>',
        'start_date': start_date,
        'end_date': end_date,
        'budget': budget or '$$',
        'travel_style': travel_style or 'balanced',
        'interests': interests or 'general sightseeing',
        'special_requirements': special_requirements or 'None',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def return_booking_form(
    form_data: Dict[str, Any],
    tool_context: ToolContext,
    instructions: Optional[str] = None,
) -> Dict[str, Any]:
    """Returns a structured JSON object for travel booking forms.
    
    Args:
        form_data (Dict[str, Any]): The form data
        tool_context (ToolContext): The context in which the tool operates
        instructions (str, optional): Instructions for processing the form
        
    Returns:
        Dict[str, Any]: A JSON dictionary for the form response
    """
    if isinstance(form_data, str):
        form_data = json.loads(form_data)

    tool_context.actions.skip_summarization = True
    tool_context.actions.escalate = True
    
    form_type = form_data.get('form_type', 'general')
    
    if form_type == 'hotel_booking':
        form_dict = {
            'type': 'form',
            'form': {
                'type': 'object',
                'properties': {
                    'hotel_name': {
                        'type': 'string',
                        'description': 'Hotel name',
                        'title': 'Hotel Name',
                    },
                    'city': {
                        'type': 'string',
                        'description': 'City where the hotel is located',
                        'title': 'City',
                    },
                    'checkin_date': {
                        'type': 'string',
                        'description': 'Check-in date (YYYY-MM-DD)',
                        'title': 'Check-in Date',
                    },
                    'checkout_date': {
                        'type': 'string',
                        'description': 'Check-out date (YYYY-MM-DD)',
                        'title': 'Check-out Date',
                    },
                    'guests': {
                        'type': 'string',
                        'description': 'Number of guests',
                        'title': 'Number of Guests',
                    },
                    'room_type': {
                        'type': 'string',
                        'description': 'Type of room',
                        'title': 'Room Type',
                    },
                    'special_requests': {
                        'type': 'string',
                        'description': 'Special requests',
                        'title': 'Special Requests',
                    },
                },
                'required': ['hotel_name', 'city', 'checkin_date', 'checkout_date', 'guests'],
            },
            'uiSchema': {
                'checkin_date': {'ui:widget': 'date'},
                'checkout_date': {'ui:widget': 'date'},
            },
            'formData': form_data,
        }
    elif form_type == 'flight_booking':
        form_dict = {
            'type': 'form',
            'form': {
                'type': 'object',
                'properties': {
                    'origin': {
                        'type': 'string',
                        'description': 'Departure city or airport',
                        'title': 'From',
                    },
                    'destination': {
                        'type': 'string',
                        'description': 'Destination city or airport',
                        'title': 'To',
                    },
                    'departure_date': {
                        'type': 'string',
                        'description': 'Departure date (YYYY-MM-DD)',
                        'title': 'Departure Date',
                    },
                    'return_date': {
                        'type': 'string',
                        'description': 'Return date (YYYY-MM-DD, optional)',
                        'title': 'Return Date',
                    },
                    'passengers': {
                        'type': 'string',
                        'description': 'Number of passengers',
                        'title': 'Passengers',
                    },
                    'travel_class': {
                        'type': 'string',
                        'description': 'Class of service',
                        'title': 'Travel Class',
                    },
                    'airline_preference': {
                        'type': 'string',
                        'description': 'Preferred airline',
                        'title': 'Airline Preference',
                    },
                },
                'required': ['origin', 'destination', 'departure_date', 'passengers'],
            },
            'uiSchema': {
                'departure_date': {'ui:widget': 'date'},
                'return_date': {'ui:widget': 'date'},
            },
            'formData': form_data,
        }
    elif form_type == 'comprehensive_itinerary':
        form_dict = {
            'type': 'form',
            'form': {
                'type': 'object',
                'properties': {
                    'destination': {
                        'type': 'string',
                        'description': 'Main travel destination',
                        'title': 'Destination',
                    },
                    'start_date': {
                        'type': 'string',
                        'description': 'Trip start date (YYYY-MM-DD)',
                        'title': 'Start Date',
                    },
                    'end_date': {
                        'type': 'string',
                        'description': 'Trip end date (YYYY-MM-DD)',
                        'title': 'End Date',
                    },
                    'budget': {
                        'type': 'string',
                        'description': 'Budget level',
                        'title': 'Budget Level',
                        'enum': ['$', '$$', '$$$', '$$$$', '$$$$$'],
                    },
                    'travel_style': {
                        'type': 'string',
                        'description': 'Style of travel',
                        'title': 'Travel Style',
                        'enum': ['luxury', 'adventure', 'cultural', 'relaxed', 'balanced'],
                    },
                    'interests': {
                        'type': 'string',
                        'description': 'Your interests (food, history, nature, etc.)',
                        'title': 'Interests',
                    },
                    'special_requirements': {
                        'type': 'string',
                        'description': 'Special needs or requirements',
                        'title': 'Special Requirements',
                    },
                },
                'required': ['destination', 'start_date', 'end_date', 'budget'],
            },
            'uiSchema': {
                'start_date': {'ui:widget': 'date'},
                'end_date': {'ui:widget': 'date'},
            },
            'formData': form_data,
        }
    else:
        # Generic form
        form_dict = {
            'type': 'form',
            'form': {
                'type': 'object',
                'properties': {
                    'request': {
                        'type': 'string',
                        'description': 'Travel request details',
                        'title': 'Travel Request',
                    },
                },
                'required': ['request'],
            },
            'formData': form_data,
        }
    
    return form_dict 

def _complete_task_on_blockchain(tool_context: ToolContext) -> Optional[Dict[str, Any]]:
    """Complete task on Aptos blockchain using async context handling.
    
    Args:
        tool_context (ToolContext): Tool context containing session information
        
    Returns:
        Optional[Dict[str, Any]]: Blockchain completion result or None if failed
    """
    try:
        # Get session_id from global agent instance
        session_id = _current_agent_instance.get_current_session_id() if _current_agent_instance else None
        
        if not session_id:
            logger.warning("No session_id available for blockchain completion")
            return None
            
        # Get Host Agent address from environment
        host_agent_address = os.environ.get('HOST_AGENT_APTOS_ADDRESS')
        if not host_agent_address:
            logger.warning("HOST_AGENT_APTOS_ADDRESS not set, cannot complete blockchain task")
            return None
        
        # Handle async context (similar to food agent pattern)
        def run_blockchain_task():
            return asyncio.run(async_complete_task_on_blockchain(session_id, host_agent_address))
        
        try:
            # Try to get current event loop
            loop = asyncio.get_running_loop()
            # If we're in an event loop, use ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                future = executor.submit(run_blockchain_task)
                result = future.result(timeout=30)  # 30 second timeout
                return result
        except RuntimeError:
            # No event loop running, use asyncio.run directly
            return asyncio.run(async_complete_task_on_blockchain(session_id, host_agent_address))
        
    except Exception as e:
        logger.error(f"Error completing task on blockchain: {e}")
        return None


async def async_complete_task_on_blockchain(session_id: str, host_agent_address: str) -> Optional[Dict[str, Any]]:
    """Async function to complete task on Aptos blockchain.
    
    Args:
        session_id (str): Current session ID
        host_agent_address (str): Host Agent Aptos address
        
    Returns:
        Optional[Dict[str, Any]]: Blockchain completion result
    """
    try:
        # Initialize Aptos configuration
        aptos_private_key = os.environ.get('APTOS_PRIVATE_KEY')
        if not aptos_private_key:
            logger.warning("APTOS_PRIVATE_KEY not set, cannot complete blockchain task")
            return None
            
        aptos_config = AptosConfig(private_key=aptos_private_key)
        aptos_task_manager = AptosTaskManager(aptos_config)
        
        # Complete task on blockchain
        result = await aptos_task_manager.complete_task(
            task_agent_address=host_agent_address,
            task_id=session_id
        )
        
        if result.get('success'):
            logger.info(f"[APTOS NETWORK] complete_task 交易发送: {result.get('tx_hash')}")
            return {
                'status': 'completed',
                'transaction_hash': result.get('tx_hash'),
                'task_id': session_id,
                'gas_used': result.get('gas_used'),
                'vm_status': result.get('vm_status')
            }
        else:
            logger.warning(f"Blockchain task completion failed: {result.get('error')}")
            return None
            
    except Exception as e:
        logger.error(f"Error in async blockchain completion: {e}")
        return None


class TravelAgent(AgentWithTaskManager):
    """An agent that handles travel services with global coverage and blockchain integration."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        global _current_agent_instance
        self._agent = self._build_agent()
        self._user_id = 'travel_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
        # Store current session_id for use in tool functions
        self._current_session_id = None
        # Set global reference
        _current_agent_instance = self

    def get_current_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._current_session_id
    
    def set_current_session_id(self, session_id: str):
        """Set the current session ID."""
        self._current_session_id = session_id

    def get_processing_message(self) -> str:
        return '正在处理您的旅行请求...'

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the travel services."""
        return LlmAgent(
            model='gemini-2.0-flash',
            name='global_travel_assistant_v1',
            description=(
                'This agent helps users plan travel, book hotels, book flights, and create comprehensive itineraries with global coverage.'
            ),
            instruction="""
你是一个专业的旅游助手，为全球旅行者提供服务。你可以帮助用户规划行程、预订酒店、预订机票和创建完整的旅行计划。

当用户询问目的地推荐时：
1. 使用search_destinations()查找符合用户需求的目的地
2. 根据用户的预算、旅行时间和偏好提供个性化推荐
3. 说明每个目的地的特色、最佳旅行季节和预算水平

当用户询问酒店信息时：
1. 使用search_hotels()搜索符合要求的酒店
2. 根据位置、价格范围、设施要求提供选择
3. 询问用户是否需要预订

当用户询问航班信息时：
1. 使用search_flights()搜索航班选项
2. 根据路线、舱位、航空公司偏好提供建议
3. 询问用户是否需要预订

当用户要预订酒店时：
1. 收集必要信息：酒店名称、城市、入住和退房日期、客人数量
2. 如果信息完整，直接调用book_hotel()完成预订
3. 如果信息不完整，使用create_hotel_booking_form()创建表单

当用户要预订机票时：
1. 收集必要信息：出发地、目的地、出发日期、乘客数量
2. 如果信息完整，直接调用book_flight()完成预订
3. 如果信息不完整，使用create_flight_booking_form()创建表单

当用户要制定完整行程时：
1. 收集信息：目的地、开始和结束日期、预算、旅行风格、兴趣
2. 如果信息完整，调用create_comprehensive_itinerary()创建完整行程
3. 如果信息不完整，使用create_itinerary_form()创建表单

当用户询问天气信息时：
1. 使用get_weather_info()获取目的地天气和季节建议
2. 提供最佳旅行时间建议

当用户询问当地景点时：
1. 使用get_local_attractions()获取景点和活动推荐
2. 根据用户兴趣提供个性化建议

重要说明：
- 酒店预订、机票预订和完整行程规划都是重要任务，会在区块链上记录完成状态
- 信息查询（目的地搜索、酒店搜索、航班搜索、天气查询、景点查询）不涉及区块链交互
- 始终以专业、友好的态度服务用户
- 提供准确的信息和实用的建议
- 考虑用户的预算和偏好
- 遵守当地法律法规和文化习俗
""",
            tools=[
                search_destinations,
                search_hotels,
                search_flights,
                get_weather_info,
                get_local_attractions,
                book_hotel,
                book_flight,
                create_comprehensive_itinerary,
                create_hotel_booking_form,
                create_flight_booking_form,
                create_itinerary_form,
                return_booking_form,
            ],
        ) 