# NCII Shield - Intake UI Description

## Overview

The admin UI provides a privacy-preserving intake system where images are hashed client-side before any data is sent to the server.

## Key Features

### 1. Dashboard View
- Shows list of active cases
- "Create New Case" button to start intake process
- Table displays: Case ID, Victim ID, Status, Created date

### 2. Multi-Step Intake Form

#### Step 1: Create Case
- **Victim ID** (required): Identifier for the victim
- **Authorization Document** (optional): Reference to authorization
- Creates case and gets case ID for subsequent steps

#### Step 2: Add Identifiers (Optional)
- Select type: Name, Handle, Alias, Email, Phone
- Enter value
- Add multiple identifiers
- Shows list of added identifiers
- Can skip if no identifiers needed

#### Step 3: Add Reference Images
- **Drag-and-drop zone** for image upload
- Supported formats: PNG, JPG, JPEG, GIF, WebP
- **Client-side hashing process**:
  1. User drops/selects image
  2. Status shows "Processing image..."
  3. Computes pHash (64-bit perceptual hash)
  4. Computes dHash (64-bit difference hash)
  5. Attempts face detection and extracts 128-dim embedding
  6. Shows "Hashing complete! Original image discarded."
  7. Displays generated hashes (hex format)
  8. Shows green confirmation: "✓ Original image discarded - only hashes retained"
- Can add multiple images
- **Original images are NEVER uploaded to server**

#### Step 4: Add Target URLs (Optional)
- Enter URLs to investigate
- Validates URL format
- Can add multiple targets
- Discovery source set to "manual"

## Security Confirmations

The UI provides clear visual feedback about privacy:

1. **Info text**: "Images are hashed client-side. Original images are never uploaded."
2. **Green checkmark**: After hashing, confirms "✓ Original discarded"
3. **Hash display**: Shows the computed hashes to admin for transparency

## Technical Implementation

### Image Hashing Module (`utils/imageHashing.ts`)
- **pHash**: 8x8 grayscale reduction, average comparison
- **dHash**: Difference hash comparing adjacent pixels
- **Face embedding**: Using face-api.js with:
  - Tiny Face Detector model
  - Face Recognition Net (128-dimensional output)
  - Face Landmark 68 Net

### Component Structure
- `IntakeForm.tsx`: Main multi-step form controller
- `ImageHasher.tsx`: Drag-drop interface with hashing logic
- Uses react-dropzone for file handling

### API Integration
- All data sent to server contains only:
  - Computed hash values (64-bit integers)
  - Optional face embedding (128 floats)
  - Metadata (labels, timestamps)
- Original pixel data never leaves the browser

## User Flow

1. Admin clicks "Create New Case"
2. Enters victim ID and optional authorization reference
3. Optionally adds identifiers (names, handles, etc.)
4. Drags reference images into drop zone
5. Sees real-time hashing progress
6. Confirms hashes generated and originals discarded
7. Optionally adds target URLs
8. Completes case creation
9. Returns to dashboard showing new case

## Visual Elements

- **Dark header**: "NCII Shield Admin Console" with tagline
- **Clean white cards**: For each form step
- **Blue primary buttons**: For main actions
- **Gray secondary buttons**: For navigation
- **Status badges**: Active (green), Resolved (blue), Suspended (red)
- **Responsive design**: Works on desktop and tablet

## Note on Face-API Models

The face detection requires model files in `/public/models/`:
- Download from face-api.js GitHub repository
- Required: tiny_face_detector, face_recognition_model, face_landmark_68_model
- See `frontend/public/models/README.md` for download instructions