import redis
import random
import time
import uuid
import math

# Redis connection
db = redis.Redis(
    host='127.0.0.1',
    port=6380,
    decode_responses=True
)

# Indian cities with their coordinates (lat, lon) and radius for random distribution
INDIAN_CITIES = {
    'Delhi': {
        'center': (28.6139, 77.2090),
        'radius_km': 30,
        'weight': 20  # More events in Delhi
    },
    'Mumbai': {
        'center': (19.0760, 72.8777),
        'radius_km': 35,
        'weight': 18
    },
    'Bangalore': {
        'center': (12.9716, 77.5946),
        'radius_km': 30,
        'weight': 18
    },
    'Hyderabad': {
        'center': (17.3850, 78.4867),
        'radius_km': 30,
        'weight': 15
    },
    'Chennai': {
        'center': (13.0827, 80.2707),
        'radius_km': 25,
        'weight': 12
    },
    'Kolkata': {
        'center': (22.5726, 88.3639),
        'radius_km': 25,
        'weight': 10
    },
    'Vizag': {
        'center': (17.6869, 83.2185),
        'radius_km': 20,
        'weight': 8
    },
    'Nellore': {
        'center': (14.4426, 79.9865),
        'radius_km': 15,
        'weight': 5
    },
    'Kadapa': {
        'center': (14.4673, 78.8242),
        'radius_km': 15,
        'weight': 5
    },
    'Kerala - Kochi': {
        'center': (9.9312, 76.2673),
        'radius_km': 25,
        'weight': 8
    },
    'Kerala - Trivandrum': {
        'center': (8.5241, 76.9366),
        'radius_km': 20,
        'weight': 6
    },
    'Pune': {
        'center': (18.5204, 73.8567),
        'radius_km': 25,
        'weight': 10
    },
    'Ahmedabad': {
        'center': (23.0225, 72.5714),
        'radius_km': 25,
        'weight': 8
    },
    'Jaipur': {
        'center': (26.9124, 75.7873),
        'radius_km': 20,
        'weight': 6
    },
    'Lucknow': {
        'center': (26.8467, 80.9462),
        'radius_km': 20,
        'weight': 5
    },
    'Chandigarh': {
        'center': (30.7333, 76.7794),
        'radius_km': 15,
        'weight': 4
    },
    'Bhopal': {
        'center': (23.2599, 77.4126),
        'radius_km': 18,
        'weight': 4
    },
    'Patna': {
        'center': (25.5941, 85.1376),
        'radius_km': 18,
        'weight': 4
    },
    'Indore': {
        'center': (22.7196, 75.8577),
        'radius_km': 18,
        'weight': 5
    },
    'Coimbatore': {
        'center': (11.0168, 76.9558),
        'radius_km': 18,
        'weight': 5
    }
}

# Event name templates
EVENT_TYPES = [
    'Tech Meetup', 'Food Festival', 'Music Concert', 'Art Exhibition',
    'Startup Event', 'Conference', 'Workshop', 'Sports Event',
    'Cultural Festival', 'Hackathon', 'Book Fair', 'Trade Show',
    'Comedy Show', 'Fashion Show', 'Auto Expo', 'Job Fair',
    'Marathon', 'Yoga Session', 'Gaming Tournament', 'Film Screening'
]

def generate_random_point(center_lat, center_lon, radius_km):
    """
    Generate a random point within radius_km of center
    Uses uniform distribution in circular area
    """
    # Convert radius to degrees (approximately)
    # 1 degree latitude ≈ 111 km
    # 1 degree longitude ≈ 111 km * cos(latitude)
    radius_lat = radius_km / 111.0
    radius_lon = radius_km / (111.0 * abs(math.cos(math.radians(center_lat))))
    
    # Generate random point in circle
    # Using square root for uniform distribution
    random_radius = random.random() ** 0.5  # Square root for uniform area distribution
    random_angle = random.random() * 2 * 3.14159265359
    
    offset_lat = random_radius * radius_lat * math.cos(random_angle)
    offset_lon = random_radius * radius_lon * math.sin(random_angle)
    
    new_lat = center_lat + offset_lat
    new_lon = center_lon + offset_lon
    
    return round(new_lat, 6), round(new_lon, 6)

def get_weighted_city():
    """Select a city based on weights (more events in bigger cities)"""
    cities = list(INDIAN_CITIES.keys())
    weights = [INDIAN_CITIES[city]['weight'] for city in cities]
    return random.choices(cities, weights=weights, k=1)[0]

def generate_event_name(city_name):
    """Generate a realistic event name"""
    event_type = random.choice(EVENT_TYPES)
    year = random.choice([2024, 2025])
    
    templates = [
        f"{city_name} {event_type} {year}",
        f"{event_type} @ {city_name}",
        f"Annual {event_type} - {city_name}",
        f"{city_name} {event_type}",
    ]
    
    return random.choice(templates)

def clear_existing_data():
    """Clear all existing events"""
    print("🗑️  Clearing existing data...")
    
    # Delete geospatial index
    db.delete('events_geo')
    
    # Delete all event hashes
    event_keys = db.keys('event:*')
    if event_keys:
        db.delete(*event_keys)
        print(f"   Deleted {len(event_keys)} existing events")
    else:
        print("   No existing events found")

def insert_events(num_events=100000, batch_size=100):
    """Insert events into Redis with geospatial indexing"""
    import math
    
    print(f"\n🚀 Inserting {num_events:,} events across India...\n")
    
    start_time = time.time()
    inserted = 0
    
    # Use pipeline for better performance
    pipeline = db.pipeline()
    
    for i in range(num_events):
        # Select city based on weights
        city_name = get_weighted_city()
        city_data = INDIAN_CITIES[city_name]
        
        # Generate random coordinates within city radius
        lat, lon = generate_random_point(
            city_data['center'][0],
            city_data['center'][1],
            city_data['radius_km']
        )
        
        # Generate event ID and name
        event_id = str(uuid.uuid4())[:8]
        event_name = generate_event_name(city_name)
        
        # Store event metadata in hash
        event_data = {
            'id': event_id,
            'name': event_name,
            'city': city_name,
            'lat': str(lat),
            'lon': str(lon),
            'created_at': str(int(time.time()))
        }
        pipeline.hset(f"event:{event_id}", mapping=event_data)
        
        # Add to geospatial index (lon, lat, member_id)
        pipeline.geoadd('events_geo', (lon, lat, event_id))
        
        inserted += 1
        
        # Execute batch every batch_size operations
        if inserted % batch_size == 0:
            pipeline.execute()
            pipeline = db.pipeline()
            
            # Progress indicator
            elapsed = time.time() - start_time
            rate = inserted / elapsed if elapsed > 0 else 0
            print(f"   Progress: {inserted:,}/{num_events:,} events ({inserted/num_events*100:.1f}%) | "
                  f"Rate: {rate:.0f} events/sec", end='\r')
    
    # Execute remaining operations
    if inserted % batch_size != 0:
        pipeline.execute()
    
    elapsed_time = time.time() - start_time
    
    print(f"\n\n✅ Successfully inserted {inserted:,} events!")
    print(f"   Time taken: {elapsed_time:.2f} seconds")
    print(f"   Average rate: {inserted/elapsed_time:.0f} events/second")
    
    return inserted

def show_statistics():
    """Show distribution of events across cities"""
    print("\n📊 Event Distribution by City:")
    print("─" * 50)
    
    total = db.zcard('events_geo')
    
    # Count events per city (approximate using pattern matching)
    city_counts = {}
    event_keys = db.keys('event:*')
    
    for key in event_keys[:1000]:  # Sample first 1000 for quick stats
        event = db.hgetall(key)
        if event and 'city' in event:
            city = event['city']
            city_counts[city] = city_counts.get(city, 0) + 1
    
    # Extrapolate to full dataset
    sample_size = min(1000, len(event_keys))
    scale_factor = total / sample_size if sample_size > 0 else 0
    
    # Sort by count
    sorted_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)
    
    for city, count in sorted_cities:
        estimated = int(count * scale_factor)
        percentage = (estimated / total * 100) if total > 0 else 0
        bar = '█' * int(percentage / 2)
        print(f"{city:20s} {estimated:5,} events ({percentage:5.1f}%) {bar}")
    
    print("─" * 50)
    print(f"{'TOTAL':20s} {total:5,} events (100.0%)")

def test_search():
    """Test search functionality"""
    print("\n🔍 Testing GEORADIUS Search...\n")
    
    # Test in Delhi
    test_cases = [
        {'name': 'Delhi (5km)', 'lat': 28.6139, 'lon': 77.2090, 'radius': 5},
        {'name': 'Delhi (20km)', 'lat': 28.6139, 'lon': 77.2090, 'radius': 20},
        {'name': 'Mumbai (10km)', 'lat': 19.0760, 'lon': 72.8777, 'radius': 10},
        {'name': 'Bangalore (15km)', 'lat': 12.9716, 'lon': 77.5946, 'radius': 15},
        {'name': 'Nellore (10km)', 'lat': 14.4426, 'lon': 79.9865, 'radius': 10},
    ]
    
    for test in test_cases:
        start = time.time()
        
        results = db.georadius(
            'events_geo',
            test['lon'],
            test['lat'],
            test['radius'],
            unit='km',
            withdist=True,
            count=100  # Limit to 100 results
        )
        
        elapsed = (time.time() - start) * 1000
        
        print(f"   {test['name']:20s} → Found {len(results):4} events in {elapsed:.2f}ms")

if __name__ == '__main__':
    print("=" * 60)
    print("  INDIAN CITIES EVENT DATA GENERATOR")
    print("=" * 60)
    
    # Clear existing data
    clear_existing_data()
    
    # Insert 10,000 events
    insert_events(num_events=100000, batch_size=100)
    
    # Show statistics
    show_statistics()
    
    # Test searches
    test_search()
    
    print("\n" + "=" * 60)
    print("✨ All done! Your Redis database now has 100K events!")
    print("=" * 60)
    print("\n💡 Next steps:")
    print("   1. Start your Flask app: python app.py")
    print("   2. Open http://localhost:5000")
    print("   3. Try searching for events in different cities!")
    print("\n")