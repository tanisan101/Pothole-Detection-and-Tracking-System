from flask import Flask, render_template, request
import pymongo
import os
from pymediainfo import MediaInfo
import re
from ultralytics import YOLO
import cv2
import math

app = Flask(__name__)

# Creating database
default_connection_url = "mongodb://localhost:27017/"
db_name = "Pothole-Detection"

try:
    client = pymongo.MongoClient(default_connection_url)
    
    # Create a DB
    dataBase = client[db_name]
    collection_name = "Potholes"
    collection = dataBase[collection_name]

except Exception as e:
    render_template("error.html", msg = "Database not connected")

# Creating upload folder
UPLOAD_FOLDER = 'Uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Creating output folder
VIDEO_DIR = 'Output'
if not os.path.exists(VIDEO_DIR):
    os.makedirs(VIDEO_DIR)

app.config['VIDEO_DIR'] = VIDEO_DIR

# Getting coordinates
def extract_gps_metadata(video_path):
    media_info = MediaInfo.parse(video_path)
    gps_data = {"Name": "Pothole"}

    for track in media_info.tracks:
        if track.track_type == "General":
            # Look for GPS coordinates in the metadata
            for key, value in track.to_data().items():
                if value and isinstance(value, str) and re.match(r'^\+[0-9]+\.[0-9]+\+[0-9]+\.[0-9]+/$', value):
                    # Example: +28.6714+077.3905/
                    gps_match = re.match(r'^\+([0-9]+\.[0-9]+)\+([0-9]+\.[0-9]+)', value)
                    if gps_match:
                        gps_data["Latitude"] = float(gps_match.group(1))
                        gps_data["Longitude"] = float(gps_match.group(2))
                        return gps_data
    
    print("No GPS metadata found.")
    gps_data["Latitude"] = None
    gps_data["Longitude"] = None
    return gps_data

# Tracking and Detection Model

def process_video(INPUT_VIDEO, OUTPUT_VIDEO, MODEL_PATH):
    cap = None
    out = None

    # Load the video and YOLO model
    cap = cv2.VideoCapture(INPUT_VIDEO)
        
    model = YOLO(MODEL_PATH)

    # Get video properties
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    # Set up the video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, fps, (frame_width, frame_height))

    frame_count = 0
    # Process video frame-by-frame
    while True:
        success, frame = cap.read()
        if not success:
            break

        # Run YOLO tracking
        results = model.track(frame, persist=True, stream=True)

        # Process detected objects
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Extract confidence score
                conf = math.ceil(box.conf[0] * 100) / 100
                
                # Only process if confidence is above threshold
                if conf > 0.2:  # Adjust threshold as needed
                    # Extract unique ID
                    if hasattr(box, 'id') and box.id is not None:
                        obj_id = int(box.id[0])
                    else:
                        obj_id = 0  # Default ID if tracking fails

                    # Extract bounding box coordinates
                    x1, y1, x2, y2 = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                    # Draw bounding box and label
                    cv2.putText(frame, f"ID:{obj_id} Score:{conf}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1, cv2.LINE_AA)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

        # Write the annotated frame
        out.write(frame)

    if cap is not None:
        cap.release()
    if out is not None:
        out.release()
    cv2.destroyAllWindows()


@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == "GET":
        potholes = list(collection.find({}, {"_id": 0, "Latitude": 1, "Longitude": 1}))
        no_of_potholes = collection.count_documents({})
        return render_template("index.html", potholes=potholes, no_of_potholes = no_of_potholes)
    
    if request.method == "POST":
        if 'video' not in request.files:
            return render_template("error.html", msg = "No file part 400")

        file = request.files['video']

        # Check if the file is selected
        if file.filename == '':
            return render_template("error.html", msg = "No selected file 400")

        # Save the file to the uploads folder
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            # Define output video path
            output_video = os.path.join(VIDEO_DIR, f"processed_{file.filename}")

            # Process the video
            model_path = r"Model\best.pt"  # Adjust the model path as needed
            try:
                process_video(filepath, output_video, model_path)
            except Exception as e:
                return render_template("error.html", msg = f"Model detection error {e}")

            gps_data = extract_gps_metadata(filepath)
            if gps_data['Latitude'] == None and gps_data["Longitude"] == None:
                return render_template("error.html", msg = "No location info")
            
            gps_data["_id"] = file.filename
            try:
                # Insert only if a document with the same key doesn't already exist
                collection.update_one(
                    {"_id": gps_data["_id"]},  # Use '_id' or a unique field to check duplicates
                    {"$setOnInsert": gps_data},  # Insert only if no match exists
                    upsert=True  # Perform an upsert but skip if duplicate
                )
                potholes = list(collection.find({}, {"_id": 0, "Latitude": 1, "Longitude": 1}))
                no_of_potholes = collection.count_documents({})
                return render_template("index.html", potholes = potholes, no_of_potholes = no_of_potholes)

            except Exception as e:
                return render_template("error.html", msg = "Mongodb error")

# Main app run
if __name__ == "__main__":
    app.run(debug=True)