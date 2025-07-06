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

# Local cache of created ride_ids for demo purposes
ride_ids = set()

# Bay Area driver database for demo
NEARBY_DRIVERS = {
    "san_francisco": [
        {"driver_id": "D001", "name": "John Chen", "rating": 4.8, "car_model": "Tesla Model 3", "license": "ABC123", "eta": "3 min", "distance": "0.2 miles"},
        {"driver_id": "D002", "name": "Maria Rodriguez", "rating": 4.9, "car_model": "Toyota Prius", "license": "XYZ789", "eta": "5 min", "distance": "0.4 miles"},
        {"driver_id": "D003", "name": "David Kim", "rating": 4.7, "car_model": "Honda Accord", "license": "DEF456", "eta": "7 min", "distance": "0.6 miles"},
        {"driver_id": "D004", "name": "Sarah Johnson", "rating": 4.6, "car_model": "Nissan Leaf", "license": "GHI789", "eta": "8 min", "distance": "0.8 miles"},
        {"driver_id": "D005", "name": "Alex Wang", "rating": 4.8, "car_model": "Chevrolet Bolt", "license": "JKL012", "eta": "10 min", "distance": "1.0 mile"}
    ],
    "oakland": [
        {"driver_id": "D006", "name": "Jennifer Lee", "rating": 4.9, "car_model": "Tesla Model Y", "license": "MNO345", "eta": "4 min", "distance": "0.3 miles"},
        {"driver_id": "D007", "name": "Michael Brown", "rating": 4.7, "car_model": "Toyota Camry", "license": "PQR678", "eta": "6 min", "distance": "0.5 miles"},
        {"driver_id": "D008", "name": "Lisa Zhang", "rating": 4.8, "car_model": "Honda Civic", "license": "STU901", "eta": "9 min", "distance": "0.7 miles"}
    ],
    "berkeley": [
        {"driver_id": "D009", "name": "Robert Garcia", "rating": 4.6, "car_model": "Hyundai Elantra", "license": "VWX234", "eta": "5 min", "distance": "0.4 miles"},
        {"driver_id": "D010", "name": "Amanda Singh", "rating": 4.8, "car_model": "Kia Optima", "license": "YZA567", "eta": "7 min", "distance": "0.6 miles"}
    ],
    "palo_alto": [
        {"driver_id": "D011", "name": "James Park", "rating": 4.9, "car_model": "BMW i3", "license": "BCD890", "eta": "6 min", "distance": "0.5 miles"},
        {"driver_id": "D012", "name": "Emily Wong", "rating": 4.7, "car_model": "Audi A3", "license": "EFG123", "eta": "8 min", "distance": "0.7 miles"}
    ]
}

# Car types and pricing
CAR_TYPES = {
    "uberx": {
        "name": "UberX",
        "description": "Affordable everyday rides",
        "capacity": "1-4 passengers",
        "base_fare": 2.55,
        "per_mile": 1.75,
        "per_minute": 0.35,
        "minimum_fare": 7.65,
        "example_cars": ["Toyota Prius", "Honda Accord", "Nissan Altima"]
    },
    "comfort": {
        "name": "Comfort",
        "description": "Newer cars with extra legroom",
        "capacity": "1-4 passengers",
        "base_fare": 3.85,
        "per_mile": 2.15,
        "per_minute": 0.40,
        "minimum_fare": 9.85,
        "example_cars": ["Toyota Camry", "Honda Accord", "Nissan Maxima"]
    },
    "xl": {
        "name": "UberXL",
        "description": "Bigger cars for up to 6 passengers",
        "capacity": "1-6 passengers",
        "base_fare": 4.85,
        "per_mile": 2.85,
        "per_minute": 0.50,
        "minimum_fare": 12.85,
        "example_cars": ["Toyota Sienna", "Honda Pilot", "Chevrolet Suburban"]
    },
    "black": {
        "name": "Uber Black",
        "description": "Premium rides in luxury cars",
        "capacity": "1-4 passengers",
        "base_fare": 8.00,
        "per_mile": 4.85,
        "per_minute": 0.80,
        "minimum_fare": 20.00,
        "example_cars": ["BMW 5 Series", "Mercedes E-Class", "Audi A6"]
    },
    "green": {
        "name": "Uber Green",
        "description": "Eco-friendly hybrid and electric vehicles",
        "capacity": "1-4 passengers",
        "base_fare": 2.55,
        "per_mile": 1.85,
        "per_minute": 0.35,
        "minimum_fare": 7.65,
        "example_cars": ["Tesla Model 3", "Toyota Prius", "Nissan Leaf"]
    }
}

# Bay Area locations and routes
BAY_AREA_LOCATIONS = {
    "san_francisco": {
        "display_name": "San Francisco",
        "popular_destinations": ["Union Square", "Fisherman's Wharf", "Golden Gate Bridge", "Chinatown", "Mission District"],
        "airports": ["SFO"],
        "traffic_zones": ["Downtown", "SOMA", "Mission", "Richmond", "Sunset"]
    },
    "oakland": {
        "display_name": "Oakland",
        "popular_destinations": ["Downtown Oakland", "Jack London Square", "Lake Merritt", "Temescal", "Rockridge"],
        "airports": ["OAK"],
        "traffic_zones": ["Downtown", "Uptown", "West Oakland", "East Oakland"]
    },
    "berkeley": {
        "display_name": "Berkeley",
        "popular_destinations": ["UC Berkeley", "Telegraph Avenue", "Fourth Street", "Solano Avenue"],
        "airports": [],
        "traffic_zones": ["Downtown Berkeley", "North Berkeley", "South Berkeley"]
    },
    "palo_alto": {
        "display_name": "Palo Alto",
        "popular_destinations": ["Stanford University", "University Avenue", "California Avenue", "Downtown Palo Alto"],
        "airports": [],
        "traffic_zones": ["Downtown", "Stanford", "Midtown"]
    }
}

# Traffic and route information
ROUTE_INFO = {
    "traffic_conditions": {
        "light": {"multiplier": 1.0, "description": "Light traffic, normal travel times"},
        "moderate": {"multiplier": 1.3, "description": "Moderate traffic, slight delays expected"},
        "heavy": {"multiplier": 1.8, "description": "Heavy traffic, significant delays"},
        "severe": {"multiplier": 2.5, "description": "Severe traffic, major delays"}
    },
    "time_of_day_factors": {
        "peak_morning": {"hours": [7, 8, 9], "factor": 1.6},
        "peak_evening": {"hours": [17, 18, 19], "factor": 1.8},
        "normal": {"factor": 1.0},
        "late_night": {"hours": [22, 23, 0, 1, 2, 3, 4, 5], "factor": 0.8}
    }
}


def search_nearby_drivers(
    pickup_location: Optional[str],
    car_type: Optional[str],
    max_distance: Optional[str]
) -> List[Dict[str, Any]]:
    """搜索附近可用司机，所有参数都是可选的。
    
    Args:
        pickup_location (str, optional): 上车地点 (如: San Francisco, Oakland)
        car_type (str, optional): 偏好车型 (uberx, comfort, xl, black, green)
        max_distance (str, optional): 最大搜索距离 (如: 1 mile, 2 miles)
        
    Returns:
        List[Dict[str, Any]]: 可用司机列表及详细信息
    """
    results = []
    
    # Determine search area
    if pickup_location:
        location_key = pickup_location.lower().replace(" ", "_")
        if location_key in NEARBY_DRIVERS:
            search_areas = [location_key]
        else:
            # If specific location not found, search all areas
            search_areas = NEARBY_DRIVERS.keys()
    else:
        # Search all areas if no location specified
        search_areas = NEARBY_DRIVERS.keys()
    
    for area in search_areas:
        for driver in NEARBY_DRIVERS[area]:
            driver_info = driver.copy()
            driver_info["area"] = area.replace("_", " ").title()
            
            # Filter by car type if specified
            if car_type and car_type.lower() in CAR_TYPES:
                car_type_info = CAR_TYPES[car_type.lower()]
                if driver_info["car_model"] not in car_type_info["example_cars"]:
                    continue
            
            # Filter by max distance if specified
            if max_distance:
                try:
                    max_dist_value = float(max_distance.split()[0])
                    driver_dist_value = float(driver_info["distance"].split()[0])
                    if driver_dist_value > max_dist_value:
                        continue
                except (ValueError, IndexError):
                    pass  # Skip distance filtering if parsing fails
                    
            results.append(driver_info)
    
    # Sort by rating (highest first), then by distance (closest first)
    results.sort(key=lambda x: (-x["rating"], float(x["distance"].split()[0])))
    return results[:10]  # Return top 10 results


def estimate_fare(
    pickup_location: str,
    destination: str,
    car_type: Optional[str],
    time_of_day: Optional[str]
) -> Dict[str, Any]:
    """估算两地之间的叫车费用，只需要起点和终点即可。
    
    Args:
        pickup_location (str): 上车地点
        destination (str): 目的地
        car_type (str, optional): 车型 (默认: uberx - 经济型)
        time_of_day (str, optional): 出行时间 (默认: 当前时间，影响高峰定价)
        
    Returns:
        Dict[str, Any]: 费用估算详情和分解
    """
    # 默认使用经济型车型
    car_type = car_type or "uberx"
    if car_type.lower() not in CAR_TYPES:
        car_type = "uberx"
    
    car_info = CAR_TYPES[car_type.lower()]
    
    # Simulate distance and time calculation (in real app, would use mapping service)
    base_distance = random.uniform(2.0, 15.0)  # Miles
    base_time = random.uniform(8, 45)  # Minutes
    
    # Apply traffic conditions based on time of day
    current_hour = datetime.now().hour if not time_of_day else None
    traffic_multiplier = 1.0
    surge_multiplier = 1.0
    
    if time_of_day:
        if time_of_day.lower() in ["morning", "rush hour morning"]:
            traffic_multiplier = 1.6
            surge_multiplier = 1.3
        elif time_of_day.lower() in ["evening", "rush hour evening"]:
            traffic_multiplier = 1.8
            surge_multiplier = 1.5
        elif time_of_day.lower() in ["night", "late night"]:
            traffic_multiplier = 0.8
            surge_multiplier = 0.9
    elif current_hour:
        if current_hour in [7, 8, 9]:
            traffic_multiplier = 1.6
            surge_multiplier = 1.3
        elif current_hour in [17, 18, 19]:
            traffic_multiplier = 1.8
            surge_multiplier = 1.5
        elif current_hour in [22, 23, 0, 1, 2, 3, 4, 5]:
            traffic_multiplier = 0.8
            surge_multiplier = 0.9
    
    # Calculate adjusted time and distance
    adjusted_time = base_time * traffic_multiplier
    distance = base_distance
    
    # Calculate fare components
    base_fare = car_info["base_fare"]
    distance_cost = distance * car_info["per_mile"]
    time_cost = adjusted_time * car_info["per_minute"]
    subtotal = base_fare + distance_cost + time_cost
    
    # Apply minimum fare
    if subtotal < car_info["minimum_fare"]:
        subtotal = car_info["minimum_fare"]
    
    # Apply surge pricing
    surge_subtotal = subtotal * surge_multiplier
    
    # Add taxes and fees (estimated)
    taxes_and_fees = surge_subtotal * 0.15  # 15% for taxes, booking fee, etc.
    total_fare = surge_subtotal + taxes_and_fees
    
    return {
        "pickup_location": pickup_location,
        "destination": destination,
        "car_type": car_info["name"],
        "distance_miles": round(distance, 1),
        "estimated_time_minutes": round(adjusted_time, 0),
        "fare_breakdown": {
            "base_fare": round(base_fare, 2),
            "distance_cost": round(distance_cost, 2),
            "time_cost": round(time_cost, 2),
            "subtotal": round(subtotal, 2),
            "surge_multiplier": surge_multiplier,
            "surge_subtotal": round(surge_subtotal, 2),
            "taxes_and_fees": round(taxes_and_fees, 2),
            "total": round(total_fare, 2)
        },
        "price_range": f"${round(total_fare * 0.9, 2)} - ${round(total_fare * 1.1, 2)}",
        "traffic_condition": "moderate" if traffic_multiplier > 1.2 else "light"
    }


def get_available_car_types(
    location: Optional[str]
) -> List[Dict[str, Any]]:
    """获取可用车型及详细信息，无需指定地点也可查询。
    
    Args:
        location (str, optional): 查询地点 (可选，默认显示所有车型)
        
    Returns:
        List[Dict[str, Any]]: 可用车型列表及详细信息
    """
    available_types = []
    
    for car_type_key, car_info in CAR_TYPES.items():
        # Add availability info (in real app, would check actual availability)
        availability = {
            "type_id": car_type_key,
            "name": car_info["name"],
            "description": car_info["description"],
            "capacity": car_info["capacity"],
            "pricing": {
                "base_fare": car_info["base_fare"],
                "per_mile": car_info["per_mile"],
                "per_minute": car_info["per_minute"],
                "minimum_fare": car_info["minimum_fare"]
            },
            "example_vehicles": car_info["example_cars"],
            "estimated_arrival": f"{random.randint(3, 12)} min",
            "available_now": True,
            "nearby_drivers": random.randint(3, 15)
        }
        
        # Simulate different availability for different car types
        if car_type_key == "black":
            availability["available_now"] = random.choice([True, False])
            availability["nearby_drivers"] = random.randint(1, 5)
        elif car_type_key == "xl":
            availability["estimated_arrival"] = f"{random.randint(8, 20)} min"
            availability["nearby_drivers"] = random.randint(2, 8)
            
        available_types.append(availability)
    
    # Sort by popularity (UberX first, then others)
    priority_order = ["uberx", "comfort", "green", "xl", "black"]
    available_types.sort(key=lambda x: priority_order.index(x["type_id"]) 
                        if x["type_id"] in priority_order else 999)
    
    return available_types


def get_route_info(
    pickup_location: str,
    destination: str,
    departure_time: Optional[str]
) -> Dict[str, Any]:
    """获取路线信息，包括距离、时间和交通状况。
    
    Args:
        pickup_location (str): 上车地点
        destination (str): 目的地
        departure_time (str, optional): 计划出发时间 (如: "now", "2:30 PM"，默认立即)
        
    Returns:
        Dict[str, Any]: 路线信息和备选路线
    """
    # Simulate route calculation (in real app, would use mapping service)
    main_distance = random.uniform(2.0, 15.0)
    main_time = random.uniform(8, 45)
    
    # Determine traffic condition based on time
    current_hour = datetime.now().hour
    if departure_time and departure_time.lower() != "now":
        # Parse departure time (simplified)
        try:
            if "AM" in departure_time.upper() or "PM" in departure_time.upper():
                time_str = departure_time.replace("AM", "").replace("PM", "").strip()
                hour = int(time_str.split(":")[0])
                if "PM" in departure_time.upper() and hour != 12:
                    hour += 12
                elif "AM" in departure_time.upper() and hour == 12:
                    hour = 0
                current_hour = hour
        except:
            pass  # Use current hour if parsing fails
    
    # Determine traffic condition
    if current_hour in [7, 8, 9, 17, 18, 19]:
        traffic_condition = "heavy"
        traffic_multiplier = 1.8
    elif current_hour in [6, 10, 16, 20]:
        traffic_condition = "moderate"
        traffic_multiplier = 1.3
    elif current_hour in [22, 23, 0, 1, 2, 3, 4, 5]:
        traffic_condition = "light"
        traffic_multiplier = 0.8
    else:
        traffic_condition = "light"
        traffic_multiplier = 1.0
    
    adjusted_time = main_time * traffic_multiplier
    
    # Generate alternative routes
    alt_route_1 = {
        "name": "Fastest Route",
        "distance_miles": round(main_distance, 1),
        "time_minutes": round(adjusted_time, 0),
        "description": "Main highways, moderate traffic"
    }
    
    alt_route_2 = {
        "name": "Shortest Route",
        "distance_miles": round(main_distance * 0.85, 1),
        "time_minutes": round(adjusted_time * 1.1, 0),
        "description": "City streets, more traffic lights"
    }
    
    alt_route_3 = {
        "name": "Scenic Route",
        "distance_miles": round(main_distance * 1.2, 1),
        "time_minutes": round(adjusted_time * 1.15, 0),
        "description": "Coastal roads, beautiful views"
    }
    
    return {
        "pickup_location": pickup_location,
        "destination": destination,
        "departure_time": departure_time or "now",
        "traffic_condition": traffic_condition,
        "traffic_description": ROUTE_INFO["traffic_conditions"][traffic_condition]["description"],
        "recommended_route": alt_route_1,
        "alternative_routes": [alt_route_2, alt_route_3],
        "total_routes_available": 3,
        "real_time_updates": True,
        "toll_roads": random.choice([True, False]),
        "estimated_toll_cost": f"${random.uniform(2.0, 8.0):.2f}" if random.choice([True, False]) else "No tolls"
    }


def request_ride(
    pickup_location: str,
    destination: str,
    car_type: Optional[str],
    passenger_count: Optional[str],
    pickup_time: Optional[str],
    special_instructions: Optional[str],
    tool_context: ToolContext
) -> Dict[str, Any]:
    """Request a ride with payment confirmation - requires blockchain task completion.
    
    只需要提供起点和终点即可叫车，其他参数无需用户设定。
    
    Args:
        pickup_location (str): 上车地点地址
        destination (str): 目的地地址  
        car_type (str, optional): 车型 (默认: uberx - 经济型)
        passenger_count (str, optional): 乘客数量 (默认: 1人)
        pickup_time (str, optional): 上车时间 (默认: 立即)
        special_instructions (str, optional): 给司机的特殊说明
        tool_context (ToolContext): 区块链完成上下文
        
    Returns:
        Dict[str, Any]: 叫车确认详情和区块链完成记录
    """
    # 设置默认值，简化用户操作
    car_type = car_type or "uberx"  # 默认经济型车型
    passenger_count = passenger_count or "1"  # 默认1人
    pickup_time = pickup_time or "now"  # 默认立即叫车
        
    # Generate unique ride ID
    ride_id = 'ride_' + str(random.randint(1000000, 9999999))
    ride_ids.add(ride_id)
    
    # Get fare estimate (use None for current time)
    fare_estimate = estimate_fare(pickup_location, destination, car_type, None)
    
    # Find available driver (simulation)
    available_drivers = search_nearby_drivers(pickup_location, car_type, "2 miles")
    if not available_drivers:
        return {
            "status": "error",
            "message": "No drivers available in your area at this time",
            "ride_id": ride_id,
            "suggested_action": "Try a different car type or wait a few minutes"
        }
    
    assigned_driver = available_drivers[0]  # Assign closest/highest rated driver
    
    # Calculate ETA and create ride confirmation
    pickup_eta = assigned_driver["eta"]
    ride_start_time = datetime.now() + timedelta(minutes=int(pickup_eta.split()[0]))
    estimated_arrival = ride_start_time + timedelta(minutes=fare_estimate["estimated_time_minutes"])
    
    ride_details = {
        "ride_id": ride_id,
        "status": "confirmed",
        "pickup_location": pickup_location,
        "destination": destination,
        "car_type": CAR_TYPES[car_type.lower()]["name"],
        "passenger_count": passenger_count,
        "pickup_time": pickup_time,
        "driver_info": {
            "name": assigned_driver["name"],
            "rating": assigned_driver["rating"],
            "car_model": assigned_driver["car_model"],
            "license_plate": assigned_driver["license"],
            "phone": f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
        },
        "timing": {
            "driver_eta": pickup_eta,
            "estimated_pickup_time": ride_start_time.strftime("%Y-%m-%d %H:%M"),
            "estimated_arrival_time": estimated_arrival.strftime("%Y-%m-%d %H:%M"),
            "total_trip_time": f"{fare_estimate['estimated_time_minutes']} minutes"
        },
        "fare_details": fare_estimate["fare_breakdown"],
        "payment_method": "Credit Card ****1234",
        "special_instructions": special_instructions or "None",
        "tracking_available": True,
        "ride_share_pin": random.randint(1000, 9999)
    }
    
    # Note: Blockchain task completion is now handled by the separate complete_ride_task tool
    
    return ride_details


def create_ride_request_form(
    pickup_location: Optional[str],
    destination: Optional[str],
    car_type: Optional[str],
    passenger_count: Optional[str],
    pickup_time: Optional[str],
    special_instructions: Optional[str]
) -> Dict[str, Any]:
    """Create a ride request form for user to fill out.
    
    Args:
        pickup_location (str, optional): Pickup location
        destination (str, optional): Destination location
        car_type (str, optional): Preferred car type
        passenger_count (str, optional): Number of passengers
        pickup_time (str, optional): Preferred pickup time
        special_instructions (str, optional): Special instructions
        
    Returns:
        Dict[str, Any]: Ride request form data
    """
    ride_id = 'ride_form_' + str(random.randint(1000000, 9999999))
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    return {
        'ride_id': ride_id,
        'pickup_location': pickup_location or '<pickup address>',
        'destination': destination or '<destination address>',
        'car_type': car_type or 'uberx',
        'passenger_count': passenger_count or '1',
        'pickup_time': pickup_time or 'now',
        'special_instructions': special_instructions or 'none',
        'request_time': current_time,
        'available_car_types': list(CAR_TYPES.keys())
    }


def complete_ride_task(tool_context: ToolContext) -> Dict[str, Any]:
    """Complete the ride task on Aptos blockchain after successful ride booking.
    
    This function should be called after a ride has been successfully booked
    to record the task completion on the Aptos blockchain.
    
    Args:
        tool_context (ToolContext): The tool context containing session information
        
    Returns:
        Dict[str, Any]: Blockchain completion result
    """
    global _current_agent_instance
    
    logger.info("[APTOS NETWORK] 🚗 start to complete the ride task on blockchain...")
    
    if not _current_agent_instance:
        logger.warning("[APTOS NETWORK] 错误: 没有当前 agent 实例")
        return {
            'status': 'failed',
            'error': 'No current agent instance available',
            'message': '区块链任务完成失败：系统错误'
        }
        
    session_id = _current_agent_instance._current_session_id
    logger.info(f"[APTOS NETWORK] current task session ID: {session_id}")
    
    if not session_id:
        logger.warning("[APTOS NETWORK] 错误: 没有会话 ID")
        return {
            'status': 'failed',
            'error': 'No session ID available',
            'message': '区块链任务完成失败：缺少会话信息'
        }
    
    # Execute blockchain completion
    try:
        blockchain_result = _complete_task_on_blockchain(tool_context)
        
        if blockchain_result and blockchain_result.get('status') == 'completed':
            tx_hash = blockchain_result.get('transaction_hash')
            logger.info(f"[APTOS NETWORK] ✅ ride task completed on blockchain! tx hash: {tx_hash}")
            
            # Generate tracking URL
            aptos_node_url = os.environ.get('APTOS_NODE_URL', 'https://fullnode.devnet.aptoslabs.com')
            if 'mainnet' in aptos_node_url:
                network = 'mainnet'
            elif 'testnet' in aptos_node_url:
                network = 'testnet'
            else:
                network = 'devnet'
            
            tracking_url = f"https://explorer.aptoslabs.com/txn/{tx_hash}?network={network}"
            
            return {
                'status': 'completed',
                'transaction_hash': tx_hash,
                'task_id': session_id,
                'tracking_url': tracking_url,
                'network': network,
                'message': f'✅ 叫车任务已在区块链上完成记录\n交易哈希: {tx_hash}\n可通过以下链接查看: {tracking_url}'
            }
        else:
            error_msg = blockchain_result.get('error', '未知错误') if blockchain_result else '区块链操作失败'
            logger.warning(f"[APTOS NETWORK] ❌ 叫车任务区块链完成失败: {error_msg}")
            return {
                'status': 'failed',
                'error': error_msg,
                'task_id': session_id,
                'message': f'⚠️ 区块链任务完成失败: {error_msg}\n叫车服务本身已正常完成'
            }
            
    except Exception as e:
        logger.error(f"[APTOS NETWORK] ❌ 区块链任务完成异常: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': session_id,
            'message': f'⚠️ 区块链任务完成异常: {str(e)}\n叫车服务本身已正常完成'
        }


def return_ride_form(
    form_data: Dict[str, Any],
    tool_context: ToolContext,
    instructions: Optional[str],
) -> Dict[str, Any]:
    """Returns a structured JSON object for the ride request form.
    
    Args:
        form_data (Dict[str, Any]): The ride request form data
        tool_context (ToolContext): The context in which the tool operates
        instructions (str, optional): Instructions for processing the form
        
    Returns:
        Dict[str, Any]: A JSON dictionary for the form response
    """
    if isinstance(form_data, str):
        form_data = json.loads(form_data)

    tool_context.actions.skip_summarization = True
    tool_context.actions.escalate = True
    
    form_dict = {
        'type': 'form',
        'form': {
            'type': 'object',
            'properties': {
                'pickup_location': {
                    'type': 'string',
                    'description': 'Pickup location address',
                    'title': 'Pickup Location',
                },
                'destination': {
                    'type': 'string',
                    'description': 'Destination address',
                    'title': 'Destination',
                },
                'car_type': {
                    'type': 'string',
                    'enum': ['uberx', 'comfort', 'xl', 'black', 'green'],
                    'description': 'Type of car service',
                    'title': 'Car Type',
                },
                'passenger_count': {
                    'type': 'string',
                    'enum': ['1', '2', '3', '4', '5', '6'],
                    'description': 'Number of passengers',
                    'title': 'Passengers',
                },
                'pickup_time': {
                    'type': 'string',
                    'description': 'Pickup time (now or specific time)',
                    'title': 'Pickup Time',
                },
                'special_instructions': {
                    'type': 'string',
                    'description': 'Special instructions for driver',
                    'title': 'Special Instructions',
                }
            },
            'required': ['pickup_location', 'destination', 'car_type'],
            'title': 'Ride Request Form'
        },
        'prefill': form_data,
        'instructions': instructions or 'Please fill out the ride request form with your pickup and destination details.'
    }
    
    return form_dict


def _complete_task_on_blockchain(tool_context: ToolContext) -> Optional[Dict[str, Any]]:
    """Complete task on Aptos blockchain (synchronous wrapper for async operation).
    
    Args:
        tool_context (ToolContext): Context containing session information
        
    Returns:
        Optional[Dict[str, Any]]: Blockchain completion result or None if failed
    """
    global _current_agent_instance
    
    # logger.info("[APTOS DEBUG] 开始区块链任务完成流程...")
    
    if not _current_agent_instance:
        # logger.warning("[APTOS DEBUG] 错误: 没有当前 agent 实例")
        return None
        
    session_id = _current_agent_instance._current_session_id
    # logger.info(f"[APTOS DEBUG] 当前会话 ID: {session_id}")
    
    if not session_id:
        logger.warning("[APTOS DEBUG] 错误: 没有会话 ID")
        return None
    
    # Handle async blockchain operation in sync context - using Food Agent pattern
    try:
        import asyncio
        import concurrent.futures
        import threading
        
        def run_blockchain_task():
            """Run blockchain task in a new event loop - same pattern as Food Agent"""
            try:
                # Create a new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    # logger.info("[APTOS DEBUG] 在新事件循环中执行区块链任务...")
                    return new_loop.run_until_complete(async_complete_task_on_blockchain(
                        session_id,
                        os.getenv('HOST_AGENT_APTOS_ADDRESS', 'unknown')
                    ))
                finally:
                    new_loop.close()
            except Exception as e:
                # logger.error(f"[APTOS DEBUG] 区块链任务线程错误: {e}")
                return {
                    'status': 'failed',
                    'error': str(e)
                }
        
        try:
            # Check if we're in an async context
            loop = asyncio.get_running_loop()
            # If we're in an event loop, run in a separate thread
            # logger.info("[APTOS DEBUG] 检测到事件循环，在独立线程中运行区块链任务...")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_blockchain_task)
                result = future.result(timeout=30)  # 30 second timeout
                # logger.info(f"[APTOS DEBUG] 区块链任务完成，结果: {result}")
                return result
                
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            logger.info("[APTOS DEBUG] 没有事件循环，在当前线程中运行...")
            result = asyncio.run(async_complete_task_on_blockchain(
                session_id,
                os.getenv('HOST_AGENT_APTOS_ADDRESS', 'unknown')
            ))
            # logger.info(f"[APTOS DEBUG] 区块链任务完成，结果: {result}")
            return result
            
    except Exception as e:
        # Log error but don't fail the ride
        logger.warning(f"[APTOS DEBUG] 区块链交互失败: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'note': 'Ride confirmed but blockchain recording failed'
        }


def _is_valid_aptos_address(address: str) -> bool:
    """验证Aptos地址格式是否正确
    
    Args:
        address: 待验证的地址字符串
        
    Returns:
        bool: 地址是否有效
    """
    if not address or not isinstance(address, str):
        return False
    
    # 移除可能的空白字符
    address = address.strip()
    
    # 检查是否以0x开头
    if not address.startswith('0x'):
        return False
    
    # 移除0x前缀
    hex_part = address[2:]
    
    # 检查长度（Aptos地址应该是64位十六进制）
    if len(hex_part) != 64:
        return False
    
    # 检查是否全部为十六进制字符
    try:
        int(hex_part, 16)
        return True
    except ValueError:
        return False


async def async_complete_task_on_blockchain(session_id: str, host_agent_address: str) -> Optional[Dict[str, Any]]:
    """Complete task on Aptos blockchain asynchronously.
    
    Args:
        session_id (str): Session ID to use as task UUID
        host_agent_address (str): Host Agent's Aptos address
        
    Returns:
        Optional[Dict[str, Any]]: Blockchain completion result
    """
    try:
        # 验证Host Agent地址有效性
        if not _is_valid_aptos_address(host_agent_address):
            logger.warning(f"[APTOS NETWORK] Host Agent地址无效: {host_agent_address}")
            logger.info("[APTOS NETWORK] 跳过区块链任务完成，业务功能正常运行")
            return {
                'status': 'skipped',
                'reason': 'invalid_host_agent_address',
                'task_id': session_id,
                'note': 'Task completed successfully, blockchain recording skipped due to invalid host agent address'
            }
        
        aptos_config = AptosConfig()
        aptos_task_manager = AptosTaskManager(aptos_config)
        
        # Use session_id directly as string for blockchain
        # logger.info(f"[APTOS NETWORK] 开始完成叫车任务，task_id: {session_id}")
        
        # Complete the task on blockchain
        result = await aptos_task_manager.complete_task(
            task_agent_address=host_agent_address,
            task_id=session_id
        )
        
        if result and 'tx_hash' in result:
            # logger.info(f"[APTOS NETWORK] 叫车任务完成! tx: {result['tx_hash']}")
            return {
                'status': 'completed',
                'transaction_hash': result['tx_hash'],
                'task_id': session_id,
                'host_agent': host_agent_address,
                'completed_at': datetime.now().isoformat()
            }
        else:
            # logger.warning("[APTOS NETWORK] 叫车任务完成失败: 没有返回交易哈希")
            return {
                'status': 'failed',
                'error': 'No transaction hash returned',
                'task_id': session_id
            }
            
    except Exception as e:
        logger.warning(f"[APTOS NETWORK] 叫车任务完成异常: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': session_id,
            'note': 'Business task completed successfully, blockchain recording failed'
        }


class UberAgent(AgentWithTaskManager):
    """An agent that handles ride-hailing services for Uber with blockchain integration."""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        global _current_agent_instance
        self._agent = self._build_agent()
        self._user_id = 'remote_agent'
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
        return "正在为您处理叫车请求..."

    def _build_agent(self) -> LlmAgent:
        return LlmAgent(
            model='gemini-2.0-flash-001',
            name='uber_agent',
            description=(
                'This agent helps users with ride-hailing services including finding drivers, estimating fares, booking rides, and route planning in the Bay Area.'
            ),
            instruction="""你是一个专业的打车助手Agent，专门为用户提供Uber叫车服务。

你的核心功能包括：
1. 查询附近可用司机和车辆信息
2. 估算不同车型的费用和到达时间
3. 提供路线规划和交通信息
4. 协助用户完成叫车预订（重要任务，需要区块链确认）

🚗 **简化叫车流程**：
- 用户只需要说："从A地到B地叫车"或"我要从X去Y"
- 系统会自动使用默认设置：
  * 车型：UberX (经济型)
  * 乘客数：1人
  * 时间：立即叫车
- 用户可以选择性地指定特殊要求（如车型、乘客数、时间等）

⛓️ **区块链任务完成流程（重要）**：
当你成功完成叫车预订后（使用 request_ride 函数返回司机信息、费用等），你必须：

1. **立即调用 complete_ride_task 函数** 来在 Aptos 区块链上记录任务完成
2. 告诉用户叫车已成功预订的同时，也要告知区块链记录状态
3. 如果区块链记录成功，提供交易追踪链接给用户
4. 如果区块链记录失败，说明叫车服务正常但区块链记录未成功

**完整的叫车响应流程**：
1. 使用 request_ride 完成叫车预订
2. 向用户显示叫车详情（司机、费用、ETA等）
3. **必须调用 complete_ride_task 完成区块链任务记录**
4. 向用户报告区块链记录状态

工作原则：
- 为用户提供准确的车辆和费用信息
- 确保叫车流程顺畅便捷，最小化用户输入
- **每次叫车成功后都必须调用 complete_ride_task 进行区块链记录**
- 始终以用户体验为优先

你主要服务于Bay Area地区（旧金山、奥克兰、伯克利、帕罗奥图）。

对于信息查询类请求（如查询司机、估算费用），直接提供信息。
对于叫车预订类请求，将进行支付确认并在区块链上记录任务完成。""",
            tools=[
                search_nearby_drivers,
                estimate_fare, 
                get_available_car_types,
                get_route_info,
                request_ride,
                create_ride_request_form,
                return_ride_form,
                complete_ride_task
            ],
        )

