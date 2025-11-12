from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import redis
import uuid
import time

app = Flask(__name__)
CORS(app)

# Redis connection
def get_db():
    return redis.Redis(
        host='127.0.0.1',
        port=6380,
        decode_responses=True
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/events/search', methods=['POST'])
def search_events():
    """Find all events within radius using Redis GEORADIUS - MUCH FASTER!"""
    data = request.json
    tracker_lat = float(data['lat'])
    tracker_lon = float(data['lon'])
    radius = float(data['radius'])
    
    start_time = time.time()
    
    db = get_db()
    
    # ═══════════════════════════════════════════════════════════
    # GEORADIUS: Find events within radius IN ONE COMMAND!
    # Only checks ~50-100 candidates instead of all 10,000!
    # ═══════════════════════════════════════════════════════════
    nearby_ids = db.georadius(
        'events_geo',           # Geospatial index name
        tracker_lon,            # Longitude (NOTE: lon first, not lat!)
        tracker_lat,            # Latitude
        radius,                 # Radius value
        unit='km',              # Unit: kilometers
        withdist=True,          # Include distance in results
        sort='ASC'              # Sort by distance (closest first)
    )
    # Redis Command: GEORADIUS events_geo 77.2090 28.6139 5 km WITHDIST ASC
    # Returns: [(event_id, distance), (event_id, distance), ...]
    
    # Fetch full details for nearby events
    nearby_events = []
    
    if nearby_ids:
        pipeline = db.pipeline()
        for event_id, distance in nearby_ids:
            pipeline.hgetall(f"event:{event_id}")
        
        event_details = pipeline.execute()
        
        # Combine event details with distance
        for (event_id, distance), details in zip(nearby_ids, event_details):
            if details:
                details['distance'] = round(float(distance), 2)
                nearby_events.append(details)
    
    processing_time = (time.time() - start_time) * 1000
    
    return jsonify({
        'events': nearby_events,
        'count': len(nearby_events),
        'time_ms': round(processing_time, 2)
    })

@app.route('/api/events/create', methods=['POST'])
def create_event():
    """Create a new event and add to geospatial index"""
    data = request.json
    event_id = str(uuid.uuid4())[:8]
    
    db = get_db()
    
    # Store event metadata in hash (same as before)
    event_data = {
        'id': event_id,
        'name': data['name'],
        'lat': str(data['lat']),
        'lon': str(data['lon']),
        'created_at': str(int(time.time()))
    }
    db.hset(f"event:{event_id}", mapping=event_data)
    
    # ═══════════════════════════════════════════════════════════
    # NEW: Add to geospatial index for fast radius searches!
    # ═══════════════════════════════════════════════════════════
    db.geoadd(
        'events_geo',              # Geospatial index name
        (data['lon'], data['lat'], event_id)  # (lon, lat, member_id)
    )
    # IMPORTANT: Redis expects (longitude, latitude) - opposite of usual order!
    # Redis Command: GEOADD events_geo 77.2090 28.6139 event_id
    
    return jsonify({
        'success': True,
        'event_id': event_id,
        'message': f'Event "{data["name"]}" created successfully'
    })

@app.route('/api/events/count', methods=['GET'])
def get_event_count():
    """Get total number of events from geospatial index"""
    db = get_db()
    
    # ═══════════════════════════════════════════════════════════
    # ZCARD: Count members in sorted set (geospatial index)
    # Much faster than db.keys('event:*')
    # ═══════════════════════════════════════════════════════════
    count = db.zcard('events_geo')
    # Redis Command: ZCARD events_geo
    
    return jsonify({'count': count})

@app.route('/api/events/clear', methods=['POST'])
def clear_events():
    """Clear all events (for testing)"""
    db = get_db()
    
    # Delete geospatial index
    db.delete('events_geo')
    
    # Delete all event hashes
    event_keys = db.keys('event:*')
    if event_keys:
        db.delete(*event_keys)
    
    return jsonify({'success': True, 'cleared': len(event_keys)})

@app.route('/api/migrate', methods=['POST'])
def migrate_to_georadius():
    """
    One-time migration: Move existing events to geospatial index
    Run this ONCE if you have existing events in Redis
    """
    db = get_db()
    
    # Get all existing events
    event_keys = db.keys('event:*')
    
    if not event_keys:
        return jsonify({
            'success': True,
            'migrated': 0,
            'message': 'No events to migrate'
        })
    
    migrated = 0
    pipeline = db.pipeline()
    
    for key in event_keys:
        event = db.hgetall(key)
        if event and 'lat' in event and 'lon' in event and 'id' in event:
            # Add to geo index
            pipeline.geoadd(
                'events_geo',
                (float(event['lon']), float(event['lat']), event['id'])
            )
            migrated += 1
    
    pipeline.execute()
    
    return jsonify({
        'success': True,
        'migrated': migrated,
        'message': f'Migrated {migrated} events to geospatial index'
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)