import json
from typing import List, Dict, Any, Callable
from datetime import datetime, timedelta

class ToolRegistry:
    def __init__(self):
        self.tools = {
            "calendar": self._normalize_date,
            "calculator": self._calculate_people,
            "web_search": self._validate_destination,
            "knowledge_base": self._lookup_preferences,
            "geolocation": self._infer_location
        }
    
    def _normalize_date(self, date_str):
        """Normalize relative dates to absolute dates"""
        if date_str.lower() == "tomorrow":
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif date_str.lower() == "next friday":
            today = datetime.now()
            days_ahead = 4 - today.weekday()  # 4 is Friday
            if days_ahead <= 0:  # If today is Friday or later
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        return None
    
    def _calculate_people(self, people_str):
        """Calculate total number of people including user"""
        try:
            if "friends" in people_str.lower():
                num_friends = int(people_str.split()[0])
                return num_friends + 1  # Include user
        except:
            pass
        return None
    
    def _validate_destination(self, destination):
        """Validate if a destination is a valid airport"""
        # This would typically call an external API
        # For now, just return True for demonstration
        return True
    
    def _lookup_preferences(self, user_id):
        """Lookup user preferences from knowledge base"""
        # This would typically query a database
        # For now, return a mock preference
        return {"seat_preference": "aisle"}
    
    def _infer_location(self, ip_address):
        """Infer location based on IP address"""
        # This would typically call a geolocation service
        # For now, return a mock location
        return "New York"
    
    def resolve(self, belief, current_beliefs):
        """Try to resolve a belief using available tools"""
        if belief == "checkin_date" and "raw_date" in current_beliefs:
            return self.tools["calendar"](current_beliefs["raw_date"])
        elif belief == "num_people" and "raw_people" in current_beliefs:
            return self.tools["calculator"](current_beliefs["raw_people"])
        elif belief == "valid_destination" and "destination" in current_beliefs:
            return self.tools["web_search"](current_beliefs["destination"])
        elif belief == "user_preferences" and "user_id" in current_beliefs:
            return self.tools["knowledge_base"](current_beliefs["user_id"])
        elif belief == "departure_city" and "ip_address" in current_beliefs:
            return self.tools["geolocation"](current_beliefs["ip_address"])
        return None

