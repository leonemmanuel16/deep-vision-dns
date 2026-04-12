"""
Prompt Builder — Constructs LLM prompts with DB schema + context.

Provides the Phi-3 model with:
- Database schema (tables and columns)
- Current date/time context
- Question from the user
- Instructions to generate read-only SQL
"""

from datetime import datetime

DB_SCHEMA = """
Tables in the database:

1. events (id UUID, camera_id UUID, zone_id UUID, event_type VARCHAR, label VARCHAR,
   confidence REAL, bbox JSONB, tracker_id INT, snapshot_url VARCHAR, clip_url VARCHAR,
   review_pass VARCHAR, needs_deep_review BOOL, attributes JSONB, person_id UUID,
   detected_at TIMESTAMPTZ, created_at TIMESTAMPTZ)
   - event_type: 'person_detected', 'vehicle_detected', 'bicycle_detected', 'animal_detected'
   - label: 'person', 'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'cat', 'dog'
   - review_pass: 'online', 'nightly', 'both'
   - attributes JSONB keys for person: ropa_sup_tipo, ropa_sup_color, ropa_inf_tipo, ropa_inf_color,
     casco (bool), chaleco (bool), mochila (bool), genero_estimado, edad_estimada, face_match_id
   - attributes JSONB keys for vehicle: tipo_vehiculo, color_vehiculo, placa_texto, marca_estimada

2. cameras (id UUID, name VARCHAR, rtsp_url VARCHAR, location VARCHAR, status VARCHAR,
   enabled BOOL, created_at TIMESTAMPTZ)
   - status: 'online', 'offline', 'error'

3. zones (id UUID, camera_id UUID, name VARCHAR, zone_type VARCHAR, points JSONB,
   direction VARCHAR, enabled BOOL)

4. known_persons (id UUID, name VARCHAR, employee_id VARCHAR, department VARCHAR,
   is_active BOOL)

5. recordings (id UUID, camera_id UUID, file_path VARCHAR, start_time TIMESTAMPTZ,
   end_time TIMESTAMPTZ, duration_seconds INT, status VARCHAR)

6. traffic_counts (id UUID, zone_id UUID, direction VARCHAR, count_in INT, count_out INT,
   hour_bucket TIMESTAMPTZ)

7. heatmap_data (id UUID, camera_id UUID, hour_bucket TIMESTAMPTZ, total_detections INT)
"""


def build_prompt(question: str) -> str:
    """Build the full prompt for the LLM."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""You are a video analytics assistant for Deep Vision by DNS.
You answer questions about security camera detections, events, and people.

Current date/time: {now}

{DB_SCHEMA}

RULES:
1. Generate a single PostgreSQL SELECT query to answer the question.
2. ONLY use SELECT — never INSERT, UPDATE, DELETE, DROP, or ALTER.
3. Always add LIMIT 100 to prevent huge result sets.
4. Use ILIKE for text searches (case-insensitive).
5. For "today" use: detected_at >= CURRENT_DATE
6. For "this week" use: detected_at >= CURRENT_DATE - INTERVAL '7 days'
7. When searching attributes JSONB, use: attributes->>'key' ILIKE '%value%'
8. When asked about a person by name, search known_persons and join with events.
9. Return the SQL inside <sql></sql> tags.
10. After the SQL, write a brief template for how to present the results in Spanish.

User question: {question}

Think step by step, then provide the SQL query."""
