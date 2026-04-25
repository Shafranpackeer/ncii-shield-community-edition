# Face-API.js Model Files

This directory needs to contain the face-api.js model files for face detection and recognition.

## Required Models

Download the following models from the face-api.js GitHub repository:
https://github.com/justadudewhohacks/face-api.js/tree/master/weights

1. **Tiny Face Detector**:
   - `tiny_face_detector_model-shard1`
   - `tiny_face_detector_model-weights_manifest.json`

2. **Face Recognition Net**:
   - `face_recognition_model-shard1`
   - `face_recognition_model-shard2`
   - `face_recognition_model-weights_manifest.json`

3. **Face Landmark 68 Net**:
   - `face_landmark_68_model-shard1`
   - `face_landmark_68_model-weights_manifest.json`

## Download Instructions

```bash
# From the frontend directory
cd public/models

# Download Tiny Face Detector
wget https://github.com/justadudewhohacks/face-api.js/raw/master/weights/tiny_face_detector_model-shard1
wget https://github.com/justadudewhohacks/face-api.js/raw/master/weights/tiny_face_detector_model-weights_manifest.json

# Download Face Recognition Model
wget https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_recognition_model-shard1
wget https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_recognition_model-shard2
wget https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_recognition_model-weights_manifest.json

# Download Face Landmark Model
wget https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_landmark_68_model-shard1
wget https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_landmark_68_model-weights_manifest.json
```

These files are required for the client-side face embedding extraction to work properly.