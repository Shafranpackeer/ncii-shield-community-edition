const https = require('https');
const fs = require('fs');
const path = require('path');

const models = [
  {
    name: 'tiny_face_detector_model-shard1',
    url: 'https://github.com/justadudewhohacks/face-api.js/raw/master/weights/tiny_face_detector_model-shard1'
  },
  {
    name: 'tiny_face_detector_model-weights_manifest.json',
    url: 'https://github.com/justadudewhohacks/face-api.js/raw/master/weights/tiny_face_detector_model-weights_manifest.json'
  },
  {
    name: 'face_recognition_model-shard1',
    url: 'https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_recognition_model-shard1'
  },
  {
    name: 'face_recognition_model-shard2',
    url: 'https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_recognition_model-shard2'
  },
  {
    name: 'face_recognition_model-weights_manifest.json',
    url: 'https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_recognition_model-weights_manifest.json'
  },
  {
    name: 'face_landmark_68_model-shard1',
    url: 'https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_landmark_68_model-shard1'
  },
  {
    name: 'face_landmark_68_model-weights_manifest.json',
    url: 'https://github.com/justadudewhohacks/face-api.js/raw/master/weights/face_landmark_68_model-weights_manifest.json'
  }
];

const modelsDir = path.join(__dirname, '..', 'public', 'models');

if (!fs.existsSync(modelsDir)) {
  fs.mkdirSync(modelsDir, { recursive: true });
}

console.log('Downloading face-api.js models...');

models.forEach((model) => {
  const filePath = path.join(modelsDir, model.name);
  const file = fs.createWriteStream(filePath);

  https.get(model.url, (response) => {
    response.pipe(file);
    file.on('finish', () => {
      file.close();
      console.log(`✓ Downloaded ${model.name}`);
    });
  }).on('error', (err) => {
    console.error(`✗ Error downloading ${model.name}:`, err);
  });
});